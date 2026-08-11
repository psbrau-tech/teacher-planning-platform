from __future__ import annotations

import re
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
_LITERACY_SOURCE_KEY = "alabama_academic_english_language_arts"
_WEEKDAY_FIELDS = ("monday", "tuesday", "wednesday", "thursday", "friday")


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

    unit_topic: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    recommended_literacy_standard_ids: list[str] = Field(min_length=1, max_length=4)
    learning_targets: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    know: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    understand: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    do_statement: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    activities: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    assessments: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    resources: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    recommended_act_reference_ids: list[str] = Field(default_factory=list, max_length=8)
    act_instructional_application: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    monday: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    tuesday: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    wednesday: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    thursday: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    friday: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    alignment_summary: str = Field(max_length=_AI_FIELD_MAX_LENGTH)


class PlanningSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_topic: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    literacy_standards: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    act_preparation: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    learning_targets: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    know: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    understand: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    do_statement: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    activities: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    assessments: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    resources: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    monday: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    tuesday: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    wednesday: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    thursday: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    friday: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
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
        "unit_topic": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "recommended_literacy_standard_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 4,
        },
        "learning_targets": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "know": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "understand": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "do_statement": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "activities": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "assessments": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "resources": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "recommended_act_reference_ids": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "act_instructional_application": {
            "type": "string",
            "maxLength": _AI_FIELD_MAX_LENGTH,
        },
        "monday": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "tuesday": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "wednesday": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "thursday": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "friday": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
        "alignment_summary": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
    },
    "required": [
        "unit_topic",
        "recommended_literacy_standard_ids",
        "learning_targets",
        "know",
        "understand",
        "do_statement",
        "activities",
        "assessments",
        "resources",
        "recommended_act_reference_ids",
        "act_instructional_application",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "alignment_summary",
    ],
    "additionalProperties": False,
}

PLANNING_INSTRUCTIONS = """You are assisting a teacher with a weekly instructional plan.
The supplied selected content standards and literacy-standard candidates are authoritative text.
Never rewrite, renumber, fabricate, summarize as if authoritative, or attribute a standard that is
not supplied. Unpack the selected content standards into teacher-reviewable Learning Targets and
Know / Understand / Do statements. Those unpacked statements are instructional interpretations,
not authoritative standards. Derive a concise Unit / Topic from the scheduled unit and lesson
context. Use imported curriculum metadata when it is useful, but improve incomplete planning fields
rather than merely repeating lesson titles.

For Literacy Standards, recommend only IDs supplied in approved_literacy_standard_candidates. Do
not create literacy-standard wording. For ACT Preparation, recommend only IDs supplied in
approved_act_reference_candidates; never invent an ACT ID or rewrite ACT reference wording. If no
ACT reference is genuinely useful, return an empty ACT ID list and a brief neutral instructional
application. Build useful activities, assessments, and resources that align with the selected
standards and scheduled lessons. For Monday through Friday, describe the instruction scheduled on
that date; return an empty string for a weekday with no scheduled lesson. Respect useful nonblank
teacher-entered text in current_teacher_plan.

Suggestions are drafts only and will not be saved unless the teacher explicitly accepts or edits
them. Do not infer, request, or include student-specific information. Do not mention student names,
grades, accommodations, IEPs, 504 plans, health, discipline, identifiable student work, or
individual performance. Return only the requested structured fields."""


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Pilot data service returned invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _required_text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=503, detail="Pilot planning data is invalid")
    return value.strip()


def _optional_text(record: JsonRecord, key: str) -> str | None:
    value = record.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


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


def _lesson_context(
    client: SupabaseRestClient,
    scheduled_rows: list[JsonRecord],
) -> dict[str, JsonRecord]:
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
        lesson_rows = _records(
            client.request(
                "GET",
                "lessons",
                params={
                    "id": f"in.({','.join(lesson_ids)})",
                    "select": (
                        "id,unit_id,title,learning_targets,know,understand,do_statement,"
                        "activities,assessments,resources"
                    ),
                },
            )
        )
        unit_ids = sorted(
            {
                _required_text(row, "unit_id")
                for row in lesson_rows
                if isinstance(row.get("unit_id"), str)
            }
        )
        unit_rows = _records(
            client.request(
                "GET",
                "curriculum_units",
                params={
                    "id": f"in.({','.join(unit_ids)})",
                    "select": "id,title",
                },
            )
        ) if unit_ids else []
    except SupabaseRestError as error:
        _raise_data_error(error, "Scheduled lesson context load")

    unit_titles = {
        _required_text(row, "id"): _required_text(row, "title") for row in unit_rows
    }
    result: dict[str, JsonRecord] = {}
    for row in lesson_rows:
        lesson_id = _required_text(row, "id")
        unit_id = _required_text(row, "unit_id")
        result[lesson_id] = {
            "unit_title": unit_titles.get(unit_id, "Imported curriculum"),
            "lesson_title": _required_text(row, "title"),
            "learning_targets": _string_list(row.get("learning_targets")),
            "know": _optional_text(row, "know"),
            "understand": _optional_text(row, "understand"),
            "do_statement": _optional_text(row, "do_statement"),
            "activities": _string_list(row.get("activities")),
            "assessments": _string_list(row.get("assessments")),
            "resources": _string_list(row.get("resources")),
        }
    return result


def _selected_standards(standards: AssignmentStandardsRead) -> list[JsonRecord]:
    selected = set(standards.selected_entry_ids)
    return [
        {"standard_entry_id": str(item.id), "code": item.code, "text": item.text}
        for item in standards.standards
        if item.id in selected
    ]


def _build_context(
    assignment: JsonRecord,
    scheduled_rows: list[JsonRecord],
    lessons: dict[str, JsonRecord],
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
    scheduled: list[JsonRecord] = []
    for row in scheduled_rows:
        lesson_id = _required_text(row, "lesson_id")
        detail = lessons.get(lesson_id, {})
        scheduled.append(
            {
                "date": _required_text(row, "school_date"),
                "unit_title": detail.get("unit_title", "Imported curriculum"),
                "lesson_title": detail.get("lesson_title", "Scheduled lesson"),
                "planned_minutes": _required_int(row, "planned_minutes"),
                "imported_learning_targets": detail.get("learning_targets", []),
                "imported_know": detail.get("know"),
                "imported_understand": detail.get("understand"),
                "imported_do": detail.get("do_statement"),
                "imported_activities": detail.get("activities", []),
                "imported_assessments": detail.get("assessments", []),
                "imported_resources": detail.get("resources", []),
            }
        )

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


def _grade_numbers(value: object) -> list[int]:
    values = value if isinstance(value, list) else [value]
    grades: set[int] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        normalized = item.replace("–", "-").strip()
        range_match = re.search(r"\b(\d{1,2})\s*-\s*(\d{1,2})\b", normalized)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            grades.update(range(min(start, end), max(start, end) + 1))
            continue
        for match in re.findall(r"\b\d{1,2}\b", normalized):
            grades.add(int(match))
    return sorted(grade for grade in grades if 1 <= grade <= 12)


def _literacy_candidates(
    client: SupabaseRestClient,
    assignment: JsonRecord,
) -> list[JsonRecord]:
    grades = _grade_numbers(assignment.get("grade_levels"))
    if not grades:
        grades = [9, 10, 11, 12]
    course_keys = [f"grade_{grade}" for grade in grades]
    try:
        source_rows = _records(
            client.request(
                "GET",
                "standard_sources",
                params={
                    "source_key": f"eq.{_LITERACY_SOURCE_KEY}",
                    "is_active": "eq.true",
                    "select": "id,approved_snapshot_id,title,edition",
                    "limit": "2",
                },
            )
        )
        if len(source_rows) != 1:
            raise HTTPException(
                status_code=503,
                detail="Approved literacy standards catalog is unavailable",
            )
        source_id = _required_text(source_rows[0], "id")
        snapshot_id = _required_text(source_rows[0], "approved_snapshot_id")
        course_rows = _records(
            client.request(
                "GET",
                "standard_courses",
                params={
                    "source_id": f"eq.{source_id}",
                    "course_key": f"in.({','.join(course_keys)})",
                    "select": "id,course_key,display_name,grade_band",
                },
            )
        )
        if not course_rows:
            raise HTTPException(
                status_code=503,
                detail="Approved literacy standards course data is unavailable",
            )
        course_ids = [_required_text(row, "id") for row in course_rows]
        entries = _records(
            client.request(
                "GET",
                "standard_entries",
                params={
                    "course_id": f"in.({','.join(course_ids)})",
                    "snapshot_id": f"eq.{snapshot_id}",
                    "strand": "eq.Recurring Standards",
                    "select": "id,course_id,code,text,strand,sequence",
                    "order": "sequence.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Literacy standards candidate load")

    grade_by_course = {
        _required_text(row, "id"): (
            _optional_text(row, "grade_band") or _required_text(row, "display_name")
        )
        for row in course_rows
    }
    candidates: list[JsonRecord] = []
    for row in entries[:32]:
        candidates.append(
            {
                "standard_entry_id": _required_text(row, "id"),
                "grade_band": grade_by_course.get(_required_text(row, "course_id")),
                "code": _required_text(row, "code"),
                "strand": _optional_text(row, "strand"),
                "authoritative_text": _required_text(row, "text"),
                "authority": "Alabama State Department of Education",
                "edition": _required_text(source_rows[0], "edition"),
            }
        )
    if not candidates:
        raise HTTPException(
            status_code=503,
            detail="Approved literacy standards candidates are unavailable",
        )
    return candidates


def _resolve_literacy_standards(
    candidates: list[JsonRecord],
    selected_ids: list[str],
) -> str:
    candidate_by_id = {
        _required_text(item, "standard_entry_id"): item for item in candidates
    }
    if not selected_ids:
        raise ValueError("At least one approved literacy standard is required")
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("Duplicate literacy standard recommendation")
    unknown = [item for item in selected_ids if item not in candidate_by_id]
    if unknown:
        raise ValueError("Unapproved literacy standard recommendation")
    lines = []
    for standard_id in selected_ids:
        item = candidate_by_id[standard_id]
        grade = item.get("grade_band") or "Applicable grade"
        lines.append(
            f"{grade} {item.get('code')} — {item.get('authoritative_text')}"
        )
    return "Alabama ELA recurring literacy standard(s):\n- " + "\n- ".join(lines)


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
        literacy_standards = _resolve_literacy_standards(
            literacy_candidates,
            model_suggestions.recommended_literacy_standard_ids,
        )
        act_entries = load_approved_act_entries(
            client,
            model_suggestions.recommended_act_reference_ids,
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
            alignment_summary=model_suggestions.alignment_summary,
        )
    except (ValidationError, ActReferenceError, ValueError) as error:
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
