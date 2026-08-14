from __future__ import annotations

from decimal import Decimal
from typing import Any, NoReturn, cast
from uuid import UUID

from fastapi import HTTPException

from .ai_openai import AiUsage
from .auth import AuthenticatedTeacher
from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="AI usage logging returned invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _raise_data_error(error: SupabaseRestError) -> NoReturn:
    if error.status_code in {401, 403}:
        raise HTTPException(status_code=403, detail="AI usage logging was denied") from error
    if error.status_code in {400, 409, 422}:
        raise HTTPException(status_code=409, detail="AI usage logging was rejected") from error
    raise HTTPException(status_code=503, detail="AI usage logging is unavailable") from error


def _required_uuid(record: JsonRecord, key: str) -> UUID:
    value = record.get(key)
    if not isinstance(value, str):
        raise HTTPException(status_code=503, detail="AI usage logging returned invalid data")
    try:
        return UUID(value)
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail="AI usage logging returned invalid data",
        ) from error


def record_ai_usage(
    client: SupabaseRestClient,
    *,
    identity: AuthenticatedTeacher,
    assignment_id: UUID | None,
    feature: str,
    model: str,
    succeeded: bool,
    usage: AiUsage | None,
) -> UUID:
    """Record bounded AI operational metadata for any governed professional user.

    Existing teacher planning calls continue to populate teacher_id and assignment context.
    Administrator-only synthesis calls populate actor_id while leaving teacher_id and assignment
    null so reporting never misrepresents an administrator as a teacher.
    """
    if identity.school_id is None:
        raise HTTPException(status_code=503, detail="Governed school context is unavailable")

    is_teacher = "teacher" in identity.roles
    payload: JsonRecord = {
        "school_id": identity.school_id,
        "actor_id": identity.subject,
        "teacher_id": identity.subject if is_teacher else None,
        "teaching_assignment_id": str(assignment_id) if assignment_id is not None else None,
        "feature": feature,
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
        _raise_data_error(error)

    if len(rows) != 1:
        raise HTTPException(status_code=503, detail="AI usage logging returned invalid data")
    return _required_uuid(rows[0], "id")
