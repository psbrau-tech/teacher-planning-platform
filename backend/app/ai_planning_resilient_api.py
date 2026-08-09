from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from .act_reference import ActReferenceError, load_act_candidate_entries, load_approved_act_entries
from .ai_openai import AiServiceError, request_structured_response
from .ai_planning_api import (
    PLANNING_INSTRUCTIONS,
    PLANNING_SUGGESTION_SCHEMA,
    CurrentPlanningFields,
    ModelPlanningSuggestion,
    PlanningSuggestion,
    PlanningSuggestionRead,
    _assignment_context,
    _build_context,
    _client,
    _lesson_context,
    _literacy_candidates,
    _record_usage,
    _required_text,
)
from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings
from .standards_api import get_assignment_standards

router = APIRouter(prefix="/api/v1/ai", tags=["ai-planning"])


def _resolve_valid_literacy(candidates: list[dict[str, object]], requested: list[str]) -> str:
    by_id = {
        _required_text(item, "standard_entry_id"): item
        for item in candidates
    }
    valid_ids: list[str] = []
    for item in requested:
        if item in by_id and item not in valid_ids:
            valid_ids.append(item)
    if not valid_ids:
        return ""
    lines: list[str] = []
    for standard_id in valid_ids:
        item = by_id[standard_id]
        grade = item.get("grade_band") or "Applicable grade"
        lines.append(f"{grade} {item.get('code')} — {item.get('authoritative_text')}")
    return "Alabama ELA recurring literacy standard(s):\n- " + "\n- ".join(lines)


def _valid_act_ids(candidates: list[dict[str, object]], requested: list[str]) -> list[str]:
    allowed = {
        str(item.get("reference_code"))
        for item in candidates
        if isinstance(item.get("reference_code"), str)
    }
    valid: list[str] = []
    for item in requested:
        if item in allowed and item not in valid:
            valid.append(item)
    return valid


@router.post(
    "/planning/{assignment_id}/week/{week_start}",
    response_model=PlanningSuggestionRead,
)
def suggest_planning_resilient(
    assignment_id: UUID,
    week_start: date,
    current: CurrentPlanningFields,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlanningSuggestionRead:
    """Return the grounded draft while failing closed on bad governed reference IDs.

    The model can recommend only bounded IDs. If it nevertheless emits an unknown
    literacy or ACT ID, that governed field is left blank rather than accepting,
    rewriting, or fabricating authoritative text. Other non-authoritative planning
    suggestions remain available for teacher review.
    """
    client = _client(identity, settings)
    standards = get_assignment_standards(assignment_id, week_start, identity, settings)
    if not standards.mapped:
        raise HTTPException(status_code=409, detail="Approved standards mapping is required")

    assignment, scheduled_rows = _assignment_context(client, assignment_id, week_start)
    if not scheduled_rows:
        raise HTTPException(
            status_code=409,
            detail="Build this week's curriculum schedule before requesting AI planning assistance",
        )
    lesson_context = _lesson_context(client, scheduled_rows)
    context = _build_context(
        assignment,
        scheduled_rows,
        lesson_context,
        standards,
        current,
    )
    literacy_candidates = _literacy_candidates(client, assignment)
    context["approved_literacy_standard_candidates"] = literacy_candidates
    try:
        act_candidates = load_act_candidate_entries(client, str(context))
    except ActReferenceError as error:
        raise HTTPException(
            status_code=503,
            detail="Approved ACT reference catalog is unavailable",
        ) from error
    context["approved_act_reference_candidates"] = [
        {
            "reference_id": item.get("reference_code"),
            "domain": item.get("domain"),
            "category": item.get("category"),
            "score_range": item.get("score_range"),
            "authoritative_text": item.get("exact_text"),
        }
        for item in act_candidates
    ]

    try:
        result = request_structured_response(
            settings=settings,
            teacher_subject=identity.subject,
            instructions=PLANNING_INSTRUCTIONS,
            context=context,
            schema_name="tpp_weekly_planning_suggestion",
            schema=PLANNING_SUGGESTION_SCHEMA,
        )
    except AiServiceError as error:
        _record_usage(
            client,
            identity=identity,
            assignment_id=assignment_id,
            model=settings.openai_model,
            succeeded=False,
            usage=None,
        )
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        model_suggestions = ModelPlanningSuggestion.model_validate(result.data)
    except ValidationError as error:
        _record_usage(
            client,
            identity=identity,
            assignment_id=assignment_id,
            model=result.usage.model,
            succeeded=False,
            usage=result.usage,
        )
        raise HTTPException(
            status_code=503,
            detail="AI planning assistance returned invalid structured planning data",
        ) from error

    literacy_standards = _resolve_valid_literacy(
        literacy_candidates,
        model_suggestions.recommended_literacy_standard_ids,
    )
    valid_act_ids = _valid_act_ids(
        act_candidates,
        model_suggestions.recommended_act_reference_ids,
    )
    try:
        act_entries = load_approved_act_entries(client, valid_act_ids) if valid_act_ids else []
    except ActReferenceError as error:
        raise HTTPException(
            status_code=503,
            detail="Approved ACT reference catalog is unavailable",
        ) from error

    if act_entries:
        resolved_lines = [
            f"{item.get('reference_code')} — {item.get('exact_text')}"
            for item in act_entries
        ]
        act_preparation = (
            "ACT College and Career Readiness connection:\n- "
            + "\n- ".join(resolved_lines)
            + "\nInstructional application: "
            + model_suggestions.act_instructional_application
        )
    elif model_suggestions.recommended_act_reference_ids:
        # The model recommended only unapproved IDs. Do not preserve its application
        # as if it had a governed ACT basis; require teacher completion instead.
        act_preparation = ""
    else:
        act_preparation = model_suggestions.act_instructional_application

    alignment_note = model_suggestions.alignment_summary
    if not literacy_standards:
        alignment_note += " Literacy Standards need teacher selection from the approved Alabama candidates."
    if model_suggestions.recommended_act_reference_ids and not valid_act_ids:
        alignment_note += " ACT Preparation needs teacher selection from approved ACT references."

    suggestions = PlanningSuggestion(
        unit_topic=model_suggestions.unit_topic,
        literacy_standards=literacy_standards,
        act_preparation=act_preparation,
        learning_targets=model_suggestions.learning_targets,
        know=model_suggestions.know,
        understand=model_suggestions.understand,
        do_statement=model_suggestions.do_statement,
        activities=model_suggestions.activities,
        assessments=model_suggestions.assessments,
        resources=model_suggestions.resources,
        monday=model_suggestions.monday,
        tuesday=model_suggestions.tuesday,
        wednesday=model_suggestions.wednesday,
        thursday=model_suggestions.thursday,
        friday=model_suggestions.friday,
        alignment_summary=alignment_note,
    )
    usage_event_id = _record_usage(
        client,
        identity=identity,
        assignment_id=assignment_id,
        model=result.usage.model,
        succeeded=True,
        usage=result.usage,
    )
    return PlanningSuggestionRead(
        usage_event_id=usage_event_id,
        model=result.usage.model,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        suggestions=suggestions,
    )
