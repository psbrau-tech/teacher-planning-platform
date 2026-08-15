from __future__ import annotations

from datetime import date
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ValidationError

from .auth import AuthenticatedTeacher, require_school_reporting_admin, require_teacher
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/friday-status", tags=["friday-status"])


class TeacherFridayStatusRow(BaseModel):
    assignment_id: str
    course_name: str
    current_week_required: bool
    current_packet_submitted: bool
    next_week_start: date
    next_week_required: bool
    next_plan_submitted: bool


class AdminFridayStatusRow(TeacherFridayStatusRow):
    school_id: str
    school_name: str
    teacher_id: str
    teacher_name: str


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Authenticated access token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _rows(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(
            status_code=503,
            detail="Friday submission status returned invalid data",
        )
    return [cast(dict[str, Any], row) for row in payload if isinstance(row, dict)]


def _source_error(error: SupabaseRestError) -> HTTPException:
    if error.status_code in {401, 403}:
        return HTTPException(status_code=403, detail="Friday submission status is not authorized")
    if error.status_code in {400, 409, 422}:
        return HTTPException(status_code=409, detail="Friday submission status source was rejected")
    return HTTPException(status_code=503, detail="Friday submission status is unavailable")


def _validate_monday(week_start: date) -> None:
    if week_start.weekday() != 0:
        raise HTTPException(status_code=422, detail="Friday status week_start must be a Monday")


@router.get("/teacher", response_model=list[TeacherFridayStatusRow])
def teacher_friday_status(
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
    week_start: Annotated[date, Query()],
) -> list[TeacherFridayStatusRow]:
    """Return the requesting teacher's class-level submitted/not-submitted Friday status."""
    _validate_monday(week_start)
    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/teacher_friday_submission_status",
            payload={"target_week_start": week_start.isoformat()},
        )
    except SupabaseRestError as error:
        raise _source_error(error) from error
    try:
        return [TeacherFridayStatusRow.model_validate(row) for row in _rows(payload)]
    except ValidationError as error:
        raise HTTPException(
            status_code=503,
            detail="Friday submission status is invalid",
        ) from error


@router.get("/admin", response_model=list[AdminFridayStatusRow])
def admin_friday_status(
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    week_start: Annotated[date, Query()],
    school_id: Annotated[str | None, Query()] = None,
) -> list[AdminFridayStatusRow]:
    """Return authorized professional teacher/class status; no student or content bodies."""
    _validate_monday(week_start)
    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/admin_friday_submission_status",
            payload={
                "target_week_start": week_start.isoformat(),
                "target_school_id": school_id,
            },
        )
    except SupabaseRestError as error:
        raise _source_error(error) from error
    try:
        return [AdminFridayStatusRow.model_validate(row) for row in _rows(payload)]
    except ValidationError as error:
        raise HTTPException(
            status_code=503,
            detail="Friday submission status is invalid",
        ) from error
