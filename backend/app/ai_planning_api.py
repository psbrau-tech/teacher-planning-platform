from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import (
    Annotated,
    Any,
    Literal,
    NoReturn,
    cast,
)
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .act_reference import (
    ActReferenceError,
    load_act_candidate_entries,
    load_approved_act_entries,
)
from .ai_openai import AiServiceError, AiUsage, request_structured_response
from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings
from .standards_api import AssignmentStandardsRead, get_assignment_standards
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/ai", tags=["ai-planning"])
JsonRecord = dict[str, Any]

_AI_FIELD_MAX_LENGTH = 4_000
_PLANNING_FEATURE = "planning_suggestion"


class CurrentPlanningFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_topic: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    literacy_standards: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    act_preparation: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    learning_targets: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    know: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    understand: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    do_statement: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    activities: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    assessments: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    resources: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    monday: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    tuesday: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    wednesday: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    thursday: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)
    friday: str = Field(default="", max_length=_AI_FIELD_MAX_LENGTH)


class ModelPlanningSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_targets: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    know: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    understand: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    do_statement: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    activities: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    assessments: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    resources: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    literacy_standards: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    recommended_act_reference_ids: list[str] = Field(default_factory=list, max_length=8)
    act_instructional_application: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    alignment_summary: str = Field(max_length=_AI_FIELD_MAX_LENGTH)


class PlanningSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_targets: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    know: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    understand: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    do_statement: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    activities: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    assessments: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    resources: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    literacy_standards: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    act_preparation: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    alignment_summary: str = Field(max_length=_AI_FIELD_MAX_LENGTH)


class PlanningSuggestionRead(BaseModel):
    usage_event_id: UUID
    model: str
    estimated_cost_usd: Decimal
    suggestions: PlanningSuggestion


class SuggestionDecisionWrite(BaseModel):
    decision: Literal["accepted", "edited", "rejected"]


class SuggestionDecisionRead(BaseModel):
    usage_event_id: UUID
    field_key: str
    decision: Literal["accepted", "edited", "rejected"]


PLANNING_SUGGESTION_SCHEMA: JsonRecord = {
    "type": "object",
    "properties": {
        "learning_targets": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "know": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "understand": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "do_statement": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "activities": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "assessments": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "resources": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "literacy_standards": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "recommended_act_reference_ids": {
            "type": "array", "items": {"type": "string"}, "maxItems": 8
        },
        "act_instructional_application": {
            "type": "string", "maxLength": _AI_FIELD_MAX_LENGTH
        },
        "alignment_summary": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
    },
    "required": [
        "learning_targets",
        "know",
        "understand",
        "do_statement",
        "activities",
        "assessments",
        "resources",
        "literacy_standards",
        "recommended_act_reference_ids",
        "act_instructional_application",
        "alignment_summary",
    ],
    "additionalProperties": False,
}

PLANNING_INSTRUCTIONS = """You are assisting a teacher with weekly instructional planning.
The selected authoritative standards in the supplied context are immutable source text. Do not
rewrite, renumber, fabricate, or attribute any standard that is not supplied. Build concise,
teacher-reviewable suggestions aligned to the selected standards, scheduled lessons, and current
planning fields. Suggestions are drafts only and will not be saved unless the teacher explicitly
accepts or edits them. Do not infer or request student-specific information. Do not mention student
names, grades, accommodations, IEPs, or individual performance. ACT references are a separate
governed first-party ACT catalog. Recommend only reference IDs supplied in
approved_act_reference_candidates; never invent an ACT ID or rewrite ACT reference wording. If no
authentic ACT connection is useful, return an empty ID list and a short neutral instructional
application. Return only the requested structured fields."""


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Pilot data service returned invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _required_text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=503, detail="Pilot planning data is invalid")
    return value.strip()


def _required_uuid(record: JsonRecord, key: str) -> UUID:
    try:
        return UUID(_required_text(record, key))
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Pilot planning data is invalid") from error


def _required_int(record: JsonRecord, key: str) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=503, detail="Pilot planning data is invalid")
    return value


def _raise_data_error(error: SupabaseRestError, operation: str) -> NoReturn:
    if error.status_code in {401, 403}:
        raise HTTPException(status_code=403, detail="Pilot planning access was denied") from error
    if error.status_code in {400, 409, 422}:
        raise HTTPException(status_code=409, detail=f"{operation} was rejected") from error
    raise HTTPException(status_code=503, detail="Pilot planning service is unavailable") from error


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _assignment_context(
    client: SupabaseRestClient,
    assignment_id: UUID,
    week_start: date,
) -> tuple[JsonRecord, list[JsonRecord]]:
    week_end = week_start + timedelta(days=4)
    try:
        assignment_rows = _records(
            client.request(
                "GET",
                "teaching_assignments",
                params={
                    "id": f"eq.{assignment_id}",
                    "select": "id,school_id,course_name,course_code,grade_levels",
                    "limit": "2",
                },
            )
        )
        scheduled_rows = _records(
            client.request(
                "GET",
                "scheduled_lessons",
                params={
                    "teaching_assignment_id": f"eq.{assignment_id}",
                    "and": (
                        f"(school_date.gte.{week_start.isoformat()},"
                        f"school_date.lte.{week_end.isoformat()})"
                    ),
                    "select": "lesson_id,school_date,planned_minutes,sequence_position",
                    "order": "school_date.asc,sequence_position.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Planning context load")
    if len(assignment_rows) != 1:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")
    return assignment_rows[0], scheduled_rows


def _lesson_titles(
    client: SupabaseRestClient,
    scheduled_rows: list[JsonRecord],
) -> dict[str, str]:
    lesson_ids = sorted(
        {
            _required_text(row, "lesson_id")
            for row in scheduled_rows
            if isinstance(row.get("lesson_id"), str)
        }
    )
    if not lesson_ids:
        return {}
    try:
        rows = _records(
            client.request(
                "GET",
                "lessons",
                params={
                    "id": f"in.({','.join(lesson_ids)})",
                    "select": "id,title",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Scheduled lesson title load")
    return {_required_text(row, "id"): _required_text(row, "title") for row in rows}


def _selected_standards(standards: AssignmentStandardsRead) -> list[JsonRecord]:
    selected = set(standards.selected_entry_ids)
    return [
        {"code": item.code, "text": item.text}
        for item in standards.standards
        if item.id in selected
    ]


def _build_context(
    assignment: JsonRecord,
    scheduled_rows: list[JsonRecord],
    lesson_titles: dict[str, str],
    standards: AssignmentStandardsRead,
    current: CurrentPlanningFields,
) -> JsonRecord:
    selected = _selected_standards(standards)
    if not selected:
        raise HTTPException(
            status_code=409,
            detail=(
                "Select at least one approved standard before requesting "
                "AI planning assistance"
            ),
        )
    scheduled = [
        {
            "date": _required_text(row, "school_date"),
            "lesson_title": lesson_titles.get(
                _required_text(row, "lesson_id"),
                "Scheduled lesson",
            ),
            "planned_minutes": _required_int(row, "planned_minutes"),
        }
        for row in scheduled_rows
    ]
    course = standards.course
    source = standards.source
    if course is None or source is None:
        raise HTTPException(status_code=409, detail="Approved standards mapping is required")
    return {
        "course": {
            "course_name": _required_text(assignment, "course_name"),
            "course_code": assignment.get("course_code"),
            "grade_levels": assignment.get("grade_levels"),
            "standards_course": course.display_name,
        },
        "standards_provenance": {
            "authority": source.authority,
            "edition": source.edition,
            "source_version": source.source_version,
            "snapshot_id": str(source.snapshot_id),
        },
        "selected_authoritative_standards": selected,
        "scheduled_lessons": scheduled,
        "current_teacher_plan": current.model_dump(),
    }


def _record_usage(
    client: SupabaseRestClient,
    *,
    identity: AuthenticatedTeacher,
    assignment_id: UUID,
    model: str,
    succeeded: bool,
    usage: AiUsage | None,
) -> UUID:
    if identity.school_id is None:
        raise HTTPException(status_code=503, detail="Teacher school context is unavailable")
    payload: JsonRecord = {
        "school_id": identity.school_id,
        "teacher_id": identity.subject,
        "teaching_assignment_id": str(assignment_id),
        "feature": _PLANNING_FEATURE,
        "model": model,
        "input_tokens": usage.input_tokens if usage is not None else 0,
        "output_tokens": usage.output_tokens if usage is not None else 0,
        "cached_tokens": usage.cached_tokens if usage is not None else 0,
        "cache_write_tokens": usage.cache_write_tokens if usage is not None else 0,
        "estimated_cost_usd": str(
            usage.estimated_cost_usd if usage is not None else Decimal("0")
        ),
        "retry_count": usage.retry_count if usage is not None else 0,
        "succeeded": succeeded,
        "accepted_by_teacher": None,
        "provider_response_id": (
            usage.provider_response_id if usage is not None else None
        ),
    }
    try:
        rows = _records(
            client.request(
                "POST",
                "ai_usage_events",
                payload=payload,
                prefer="return=representation",
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "AI usage logging")
    if len(rows) != 1:
        raise HTTPException(status_code=503, detail="AI usage logging returned invalid data")
    return _required_uuid(rows[0], "id")


@router.post(
    "/planning/{assignment_id}/week/{week_start}",
    response_model=PlanningSuggestionRead,
)
def suggest_planning(
    assignment_id: UUID,
    week_start: date,
    current: CurrentPlanningFields,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlanningSuggestionRead:
    client = _client(identity, settings)
    standards = get_assignment_standards(assignment_id, week_start, identity, settings)
    if not standards.mapped:
        raise HTTPException(status_code=409, detail="Approved standards mapping is required")
    assignment, scheduled_rows = _assignment_context(client, assignment_id, week_start)
    lesson_titles = _lesson_titles(client, scheduled_rows)
    context = _build_context(assignment, scheduled_rows, lesson_titles, standards, current)
    try:
        act_candidates = load_act_candidate_entries(client, str(context))
    except ActReferenceError as error:
        raise HTTPException(
            status_code=503, detail="Approved ACT reference catalog is unavailable"
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
        try:
            _record_usage(
                client,
                identity=identity,
                assignment_id=assignment_id,
                model=settings.openai_model,
                succeeded=False,
                usage=None,
            )
        except HTTPException as logging_error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "AI planning assistance failed and its usage record "
                    "could not be saved"
                ),
            ) from logging_error
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        model_suggestions = ModelPlanningSuggestion.model_validate(result.data)
        act_entries = load_approved_act_entries(
            client, model_suggestions.recommended_act_reference_ids
        )
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
        else:
            act_preparation = model_suggestions.act_instructional_application
        suggestions = PlanningSuggestion(
            learning_targets=model_suggestions.learning_targets,
            know=model_suggestions.know,
            understand=model_suggestions.understand,
            do_statement=model_suggestions.do_statement,
            activities=model_suggestions.activities,
            assessments=model_suggestions.assessments,
            resources=model_suggestions.resources,
            literacy_standards=model_suggestions.literacy_standards,
            act_preparation=act_preparation,
            alignment_summary=model_suggestions.alignment_summary,
        )
    except (ValidationError, ActReferenceError) as error:
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
            detail="AI planning assistance returned invalid or unapproved reference data",
        ) from error

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


@router.put(
    "/usage/{usage_event_id}/decision/{field_key}",
    response_model=SuggestionDecisionRead,
)
def record_suggestion_decision(
    usage_event_id: UUID,
    field_key: str,
    payload: SuggestionDecisionWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SuggestionDecisionRead:
    client = _client(identity, settings)
    try:
        result = client.request(
            "POST",
            "rpc/record_ai_suggestion_decision",
            payload={
                "target_event_id": str(usage_event_id),
                "target_field_key": field_key,
                "target_decision": payload.decision,
            },
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "AI suggestion decision save")
    if result != payload.decision:
        raise HTTPException(status_code=503, detail="AI suggestion decision save failed")
    return SuggestionDecisionRead(
        usage_event_id=usage_event_id,
        field_key=field_key,
        decision=payload.decision,
    )
