from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from . import ai_planning_api as core
from .act_reference import ActReferenceError, load_act_candidate_entries, load_approved_act_entries
from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/ai", tags=["ai-planning"])


def _resolve_valid_literacy(candidates: list[dict[str, object]], requested: list[str]) -> str:
    by_id = {
        core._required_text(candidate, "standard_entry_id"): candidate
        for candidate in candidates
    }
    valid_ids: list[str] = []
    for requested_id in requested:
        if requested_id in by_id and requested_id not in valid_ids:
            valid_ids.append(requested_id)
    if not valid_ids:
        return ""
    lines: list[str] = []
    for standard_id in valid_ids:
        entry = by_id[standard_id]
        grade = entry.get("grade_band") or "Applicable grade"
        lines.append(f"{grade} {entry.get('code')} — {entry.get('authoritative_text')}")
    return "Alabama ELA recurring literacy standard(s):\n- " + "\n- ".join(lines)


def _valid_act_ids(candidates: list[dict[str, object]], requested: list[str]) -> list[str]:
    allowed = {
        str(candidate.get("reference_code"))
        for candidate in candidates
        if isinstance(candidate.get("reference_code"), str)
    }
    valid: list[str] = []
    for requested_id in requested:
        if requested_id in allowed and requested_id not in valid:
            valid.append(requested_id)
    return valid


@router.post(
    "/planning/{assignment_id}/week/{week_start}",
    response_model=core.PlanningSuggestionRead,
)
def suggest_planning_resilient(
    assignment_id: UUID,
    week_start: date,
    current: core.CurrentPlanningFields,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> core.PlanningSuggestionRead:
    """Return grounded planning while rejecting unknown governed reference IDs."""
    client = core._client(identity, settings)
    standards = core.get_assignment_standards(assignment_id, week_start, identity, settings)
    if not standards.mapped:
        raise HTTPException(status_code=409, detail="Approved standards mapping is required")

    assignment, scheduled_rows = core._assignment_context(client, assignment_id, week_start)
    if not scheduled_rows:
        raise HTTPException(
            status_code=409,
            detail="Build this week's curriculum schedule before requesting AI planning assistance",
        )
    lesson_context = core._lesson_context(client, scheduled_rows)
    context = core._build_context(
        assignment,
        scheduled_rows,
        lesson_context,
        standards,
        current,
    )
    literacy_candidates = core._literacy_candidates(client, assignment)
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
        result = core.request_structured_response(
            settings=settings,
            teacher_subject=identity.subject,
            instructions=core.PLANNING_INSTRUCTIONS,
            context=context,
            schema_name="tpp_weekly_planning_suggestion",
            schema=core.PLANNING_SUGGESTION_SCHEMA,
        )
    except core.AiServiceError as error:
        core._record_usage(
            client,
            identity=identity,
            assignment_id=assignment_id,
            model=settings.openai_model,
            succeeded=False,
            usage=None,
        )
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        model_suggestions = core.ModelPlanningSuggestion.model_validate(result.data)
    except ValidationError as error:
        core._record_usage(
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
        act_preparation = ""
    else:
        act_preparation = model_suggestions.act_instructional_application

    alignment_note = model_suggestions.alignment_summary
    if not literacy_standards:
        alignment_note += (
            " Literacy Standards need teacher selection from the approved Alabama candidates."
        )
    if model_suggestions.recommended_act_reference_ids and not valid_act_ids:
        alignment_note += " ACT Preparation needs teacher selection from approved ACT references."

    suggestions = core.PlanningSuggestion(
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
    usage_event_id = core._record_usage(
        client,
        identity=identity,
        assignment_id=assignment_id,
        model=result.usage.model,
        succeeded=True,
        usage=result.usage,
    )
    return core.PlanningSuggestionRead(
        usage_event_id=usage_event_id,
        model=result.usage.model,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        suggestions=suggestions,
    )
