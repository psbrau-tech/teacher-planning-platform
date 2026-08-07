from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .ai_openai import AiServiceError, request_structured_response
from .ai_usage import record_ai_usage
from .auth import AuthenticatedTeacher, require_teacher
from .friday_validation_api import get_friday_validation
from .settings import Settings, get_settings
from .standards_api import get_assignment_standards
from .supabase_rest import SupabaseRestClient
from .weekly_draft_api import get_weekly_draft

router = APIRouter(prefix="/api/v1/ai", tags=["ai-reflection"])
JsonObject = dict[str, Any]
_REFLECTION_FEATURE = "weekly_reflection"
_REFLECTION_MAX_LENGTH = 4_000


class ReflectionSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekly_reflection: str = Field(max_length=_REFLECTION_MAX_LENGTH)


class ReflectionSuggestionRead(BaseModel):
    usage_event_id: UUID
    model: str
    estimated_cost_usd: Decimal
    suggestions: ReflectionSuggestion


REFLECTION_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {
        "weekly_reflection": {
            "type": "string",
            "maxLength": _REFLECTION_MAX_LENGTH,
        }
    },
    "required": ["weekly_reflection"],
    "additionalProperties": False,
}

REFLECTION_INSTRUCTIONS = """You are assisting a teacher with a concise weekly instructional
reflection. Use only the saved weekly plan, finalized Friday validation, and selected authoritative
standards supplied in the context. Describe what instruction was completed or changed, what needs
adjustment or carry-forward, and one practical next-week priority. This is a teacher-reviewable draft
only. Do not invent student performance evidence, student names, grades, accommodations, IEPs, or
other student-specific facts. Do not rewrite or fabricate authoritative standards. Return only the
requested structured field."""


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _reflection_context(
    assignment_id: UUID,
    week_start: date,
    identity: AuthenticatedTeacher,
    settings: Settings,
) -> JsonObject:
    draft = get_weekly_draft(str(assignment_id), week_start, identity, settings)
    validation = get_friday_validation(assignment_id, week_start, identity, settings)
    standards = get_assignment_standards(assignment_id, week_start, identity, settings)

    selected_ids = set(standards.selected_entry_ids)
    selected_standards = [
        {"code": standard.code, "text": standard.text}
        for standard in standards.standards
        if standard.id in selected_ids
    ]
    source = standards.source
    provenance: JsonObject | None = None
    if source is not None:
        provenance = {
            "authority": source.authority,
            "edition": source.edition,
            "source_version": source.source_version,
            "snapshot_id": str(source.snapshot_id),
        }

    return {
        "saved_weekly_plan": draft.content,
        "saved_weekly_plan_revision": draft.revision,
        "finalized_friday_validation": validation.model_dump(mode="json"),
        "selected_authoritative_standards": selected_standards,
        "standards_provenance": provenance,
    }


@router.post(
    "/reflection/{assignment_id}/week/{week_start}",
    response_model=ReflectionSuggestionRead,
)
def suggest_weekly_reflection(
    assignment_id: UUID,
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReflectionSuggestionRead:
    client = _client(identity, settings)
    context = _reflection_context(assignment_id, week_start, identity, settings)

    try:
        result = request_structured_response(
            settings=settings,
            teacher_subject=identity.subject,
            instructions=REFLECTION_INSTRUCTIONS,
            context=context,
            schema_name="tpp_weekly_reflection_suggestion",
            schema=REFLECTION_SCHEMA,
        )
    except AiServiceError as error:
        try:
            record_ai_usage(
                client,
                identity=identity,
                assignment_id=assignment_id,
                feature=_REFLECTION_FEATURE,
                model=settings.openai_model,
                succeeded=False,
                usage=None,
            )
        except HTTPException as logging_error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "AI reflection assistance failed and its usage record "
                    "could not be saved"
                ),
            ) from logging_error
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        suggestions = ReflectionSuggestion.model_validate(result.data)
    except ValidationError as error:
        record_ai_usage(
            client,
            identity=identity,
            assignment_id=assignment_id,
            feature=_REFLECTION_FEATURE,
            model=result.usage.model,
            succeeded=False,
            usage=result.usage,
        )
        raise HTTPException(
            status_code=503,
            detail="AI reflection assistance returned invalid structured data",
        ) from error

    usage_event_id = record_ai_usage(
        client,
        identity=identity,
        assignment_id=assignment_id,
        feature=_REFLECTION_FEATURE,
        model=result.usage.model,
        succeeded=True,
        usage=result.usage,
    )
    return ReflectionSuggestionRead(
        usage_event_id=usage_event_id,
        model=result.usage.model,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        suggestions=suggestions,
    )
