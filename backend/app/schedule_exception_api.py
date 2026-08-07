from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings
from .supabase_persistence import PersistenceError, SupabaseTeachingAssignmentStore
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/schedule-exceptions", tags=["planning"])


class ScheduleExceptionWrite(BaseModel):
    is_available: bool = False
    instructional_minutes: int | None = Field(default=None, ge=1, le=1440)
    reason: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_minutes(self) -> "ScheduleExceptionWrite":
        if self.is_available and self.instructional_minutes is None:
            raise ValueError("instructional_minutes is required when the day remains available")
        return self


class ScheduleExceptionRead(BaseModel):
    id: UUID
    teaching_assignment_id: UUID
    exception_date: date
    is_available: bool
    instructional_minutes: int | None
    reason: str


JsonRecord = dict[str, Any]


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Pilot data service returned invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _raise_data_error(error: SupabaseRestError, operation: str) -> NoReturn:
    if error.status_code in {401, 403}:
        raise HTTPException(status_code=403, detail="Pilot data access was denied") from error
    if error.status_code in {400, 409, 422}:
        raise HTTPException(status_code=409, detail=f"{operation} was rejected") from error
    raise HTTPException(status_code=503, detail="Pilot data service is unavailable") from error


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _require_assignment(
    client: SupabaseRestClient,
    identity: AuthenticatedTeacher,
    assignment_id: UUID,
) -> None:
    store = SupabaseTeachingAssignmentStore(client, identity.subject)
    try:
        assignment = store.get(identity.subject, str(assignment_id))
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if assignment is None:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")


def _to_read(record: JsonRecord) -> ScheduleExceptionRead:
    try:
        return ScheduleExceptionRead(
            id=UUID(str(record["id"])),
            teaching_assignment_id=UUID(str(record["teaching_assignment_id"])),
            exception_date=date.fromisoformat(str(record["exception_date"])),
            is_available=record.get("is_available") is True,
            instructional_minutes=(
                record.get("instructional_minutes")
                if isinstance(record.get("instructional_minutes"), int)
                else None
            ),
            reason=str(record["reason"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Pilot data service returned invalid data") from error


@router.get("", response_model=list[ScheduleExceptionRead])
def list_schedule_exceptions(
    assignment_id: UUID,
    week_start: Annotated[date, Query()],
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ScheduleExceptionRead]:
    client = _client(identity, settings)
    _require_assignment(client, identity, assignment_id)
    week_end = week_start + timedelta(days=4)
    try:
        rows = _records(
            client.request(
                "GET",
                "schedule_exceptions",
                params={
                    "teaching_assignment_id": f"eq.{assignment_id}",
                    "and": (
                        f"(exception_date.gte.{week_start.isoformat()},"
                        f"exception_date.lte.{week_end.isoformat()})"
                    ),
                    "select": (
                        "id,teaching_assignment_id,exception_date,is_available,"
                        "instructional_minutes,reason"
                    ),
                    "order": "exception_date.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Schedule exception load")
    return [_to_read(row) for row in rows]


@router.put("/{assignment_id}/{exception_date}", response_model=ScheduleExceptionRead)
def upsert_schedule_exception(
    assignment_id: UUID,
    exception_date: date,
    payload: ScheduleExceptionWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ScheduleExceptionRead:
    client = _client(identity, settings)
    _require_assignment(client, identity, assignment_id)
    try:
        rows = _records(
            client.request(
                "POST",
                "schedule_exceptions",
                params={"on_conflict": "teaching_assignment_id,exception_date"},
                payload={
                    "teaching_assignment_id": str(assignment_id),
                    "exception_date": exception_date.isoformat(),
                    "is_available": payload.is_available,
                    "instructional_minutes": (
                        payload.instructional_minutes if payload.is_available else None
                    ),
                    "reason": payload.reason.strip(),
                    "created_by": identity.subject,
                },
                prefer="resolution=merge-duplicates,return=representation",
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Schedule exception save")
    if len(rows) != 1:
        raise HTTPException(status_code=503, detail="Schedule exception save returned invalid data")
    return _to_read(rows[0])


@router.delete("/{assignment_id}/{exception_date}")
def delete_schedule_exception(
    assignment_id: UUID,
    exception_date: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, bool]:
    client = _client(identity, settings)
    _require_assignment(client, identity, assignment_id)
    try:
        client.request(
            "DELETE",
            "schedule_exceptions",
            params={
                "teaching_assignment_id": f"eq.{assignment_id}",
                "exception_date": f"eq.{exception_date.isoformat()}",
            },
            prefer="return=minimal",
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Schedule exception delete")
    return {"deleted": True}
