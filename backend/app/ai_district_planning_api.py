from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .ai_openai import AiServiceError, request_structured_response
from .ai_planning_api import (
    CurrentPlanningFields,
    _assignment_context,
    _build_context,
    _client,
    _lesson_context,
    _record_usage,
)
from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings
from .standards_api import get_assignment_standards

router = APIRouter(prefix="/api/v1/ai", tags=["ai-planning"])
JsonRecord = dict[str, Any]
_AI_FIELD_MAX_LENGTH = 4_000
_DAY_SUFFIXES = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri"}
_WAG_PREFIXES = ("clt", "rrt", "cfu", "ri", "sic", "esl")

DISTRICT_FIELD_KEYS = (
    "plds",
    "misconceptions",
    "formative",
    "summative",
    "performance_task",
    "clt_mon",
    "clt_tue",
    "clt_wed",
    "clt_thu",
    "clt_fri",
    "rrt_mon",
    "rrt_tue",
    "rrt_wed",
    "rrt_thu",
    "rrt_fri",
    "cfu_mon",
    "cfu_tue",
    "cfu_wed",
    "cfu_thu",
    "cfu_fri",
    "ri_mon",
    "ri_tue",
    "ri_wed",
    "ri_thu",
    "ri_fri",
    "sic_mon",
    "sic_tue",
    "sic_wed",
    "sic_thu",
    "sic_fri",
    "esl_mon",
    "esl_tue",
    "esl_wed",
    "esl_thu",
    "esl_fri",
)


class DistrictPlanningSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plds: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    misconceptions: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    formative: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    summative: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    performance_task: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    clt_mon: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    clt_tue: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    clt_wed: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    clt_thu: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    clt_fri: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    rrt_mon: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    rrt_tue: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    rrt_wed: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    rrt_thu: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    rrt_fri: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    cfu_mon: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    cfu_tue: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    cfu_wed: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    cfu_thu: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    cfu_fri: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    ri_mon: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    ri_tue: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    ri_wed: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    ri_thu: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    ri_fri: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    sic_mon: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    sic_tue: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    sic_wed: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    sic_thu: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    sic_fri: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    esl_mon: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    esl_tue: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    esl_wed: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    esl_thu: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    esl_fri: str = Field(max_length=_AI_FIELD_MAX_LENGTH)
    alignment_summary: str = Field(max_length=_AI_FIELD_MAX_LENGTH)


class DistrictPlanningSuggestionRead(BaseModel):
    usage_event_id: UUID
    model: str
    estimated_cost_usd: Decimal
    suggestions: DistrictPlanningSuggestion


DISTRICT_PLANNING_SCHEMA: JsonRecord = {
    "type": "object",
    "properties": {
        **{
            key: {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH}
            for key in DISTRICT_FIELD_KEYS
        },
        "alignment_summary": {"type": "string", "maxLength": _AI_FIELD_MAX_LENGTH},
    },
    "required": [*DISTRICT_FIELD_KEYS, "alignment_summary"],
    "additionalProperties": False,
}

DISTRICT_PLANNING_INSTRUCTIONS = """You are assisting a teacher with the district-required
Instructional Planning Framework and Week at a Glance portions of a weekly lesson plan.

Use only the supplied scheduled lessons, selected authoritative standards, imported curriculum
metadata, and current teacher planning text. The selected standards are authoritative text; never
rewrite, renumber, fabricate, or attribute standards that were not supplied. Everything you produce
here is a teacher-reviewable instructional interpretation, not authoritative standards wording.

Complete the five Framework detail fields:
- plds: a concise teacher-usable proficiency scale or performance-level description for this week;
- misconceptions: likely class-level misconceptions or errors tied to the planned content;
- formative: practical formative checks aligned to the scheduled instruction;
- summative: an appropriate summative assessment or a concise statement that no separate summative
  assessment is planned this week, with the evidence that will be used instead;
- performance_task: an authentic application or performance task aligned to the planned content.

Complete the Week at a Glance only for weekdays that actually contain scheduled instruction. Return
an empty string for every cell on an unscheduled weekday. For each scheduled day:
- clt: clear learning target and success criteria specific to that day's lesson;
- rrt: rigorous and relevant task;
- cfu: checks for understanding;
- ri: responsive instruction described at the class/group level, never for an identified student;
- sic: concrete routines, expectations, questioning, collaboration, or practice structures that
  support a strong instructional culture;
- esl: observable evidence of learning the teacher can collect during or at the end of instruction.

Avoid generic boilerplate when the supplied lesson context supports something more specific. Do not
infer, request, or include student-specific information. Do not mention student names, identifiers,
grades, accommodations, IEPs, 504 plans, health, discipline, identifiable student work, or
individual performance. Suggestions are drafts only and are not saved unless the teacher explicitly
accepts or edits them. Return only the requested structured fields."""


def _scheduled_day_suffixes(scheduled_rows: list[JsonRecord]) -> set[str]:
    suffixes: set[str] = set()
    for row in scheduled_rows:
        raw_date = row.get("school_date")
        if not isinstance(raw_date, str):
            continue
        try:
            weekday = date.fromisoformat(raw_date).weekday()
        except ValueError:
            continue
        suffix = _DAY_SUFFIXES.get(weekday)
        if suffix is not None:
            suffixes.add(suffix)
    return suffixes


def _clear_unscheduled_weekdays(
    suggestions: DistrictPlanningSuggestion,
    scheduled_rows: list[JsonRecord],
) -> DistrictPlanningSuggestion:
    scheduled_suffixes = _scheduled_day_suffixes(scheduled_rows)
    updates: dict[str, str] = {}
    for suffix in _DAY_SUFFIXES.values():
        if suffix in scheduled_suffixes:
            continue
        for prefix in _WAG_PREFIXES:
            updates[f"{prefix}_{suffix}"] = ""
    return suggestions.model_copy(update=updates)


@router.post(
    "/district-planning/{assignment_id}/week/{week_start}",
    response_model=DistrictPlanningSuggestionRead,
)
def suggest_district_planning(
    assignment_id: UUID,
    week_start: date,
    current: CurrentPlanningFields,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DistrictPlanningSuggestionRead:
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
    if not scheduled_rows:
        raise HTTPException(
            status_code=409,
            detail="Build this week's curriculum schedule before requesting AI planning assistance",
        )

    try:
        result = request_structured_response(
            settings=settings,
            teacher_subject=identity.subject,
            instructions=DISTRICT_PLANNING_INSTRUCTIONS,
            context=context,
            schema_name="tpp_district_weekly_planning_suggestion",
            schema=DISTRICT_PLANNING_SCHEMA,
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
                    "AI district planning assistance failed and its usage record could not be saved"
                ),
            ) from logging_error
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        suggestions = DistrictPlanningSuggestion.model_validate(result.data)
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
            detail="AI district planning assistance returned invalid structured data",
        ) from error

    suggestions = _clear_unscheduled_weekdays(suggestions, scheduled_rows)
    usage_event_id = _record_usage(
        client,
        identity=identity,
        assignment_id=assignment_id,
        model=result.usage.model,
        succeeded=True,
        usage=result.usage,
    )
    return DistrictPlanningSuggestionRead(
        usage_event_id=usage_event_id,
        model=result.usage.model,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        suggestions=suggestions,
    )
