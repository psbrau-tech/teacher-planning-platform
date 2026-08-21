from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings
from .supabase_persistence import PersistenceError, SupabaseTeachingAssignmentStore
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/plans/lessons", tags=["planning"])


class PlannedLessonMove(BaseModel):
    lesson_date: date


class PlannedLessonMoveRead(BaseModel):
    scheduled_lesson_id: UUID
    lesson_date: date


class PlannedLessonReplacement(BaseModel):
    replacement_kind: str
    manual_unit_title: str | None = Field(default=None, max_length=300)
    manual_lesson_title: str | None = Field(default=None, max_length=1000)
    manual_learning_targets: list[str] = Field(default_factory=list)
    manual_assessment: str | None = Field(default=None, max_length=2000)
    original_disposition: str | None = None

    @model_validator(mode="after")
    def validate_replacement(self) -> PlannedLessonReplacement:
        if self.replacement_kind not in {"next", "manual"}:
            raise ValueError("replacement_kind must be next or manual")
        if self.replacement_kind == "manual":
            if not (self.manual_unit_title or "").strip() or not (
                self.manual_lesson_title or ""
            ).strip():
                raise ValueError("Manual unit/topic and lesson/focus are required")
            if self.original_disposition not in {"skip", "postpone"}:
                raise ValueError("Choose whether to skip or postpone the original lesson")
            if len(self.manual_learning_targets) > 20 or any(
                len(target.strip()) > 1000 for target in self.manual_learning_targets
            ):
                raise ValueError("Use no more than 20 learning targets of 1,000 characters each")
            self.manual_learning_targets = [
                target.strip() for target in self.manual_learning_targets if target.strip()
            ]
        return self


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Pilot planning data is unavailable")
    return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


@router.patch("/{scheduled_lesson_id}", response_model=PlannedLessonMoveRead)
def move_planned_lesson(
    scheduled_lesson_id: UUID,
    payload: PlannedLessonMove,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlannedLessonMoveRead:
    """Move one scheduled lesson to another available meeting day in the same week."""
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    client = SupabaseRestClient.from_settings(settings, access_token=identity.access_token)
    try:
        rows = _records(
            client.request(
                "GET",
                "scheduled_lessons",
                params={
                    "id": f"eq.{scheduled_lesson_id}",
                    "select": "id,teaching_assignment_id,school_date",
                    "limit": "1",
                },
            )
        )
    except SupabaseRestError as error:
        raise HTTPException(status_code=503, detail="Planned lesson could not be loaded") from error
    if len(rows) != 1:
        raise HTTPException(status_code=404, detail="Planned lesson not found")

    row = rows[0]
    assignment_id = row.get("teaching_assignment_id")
    original_date = row.get("school_date")
    if not isinstance(assignment_id, str) or not isinstance(original_date, str):
        raise HTTPException(status_code=503, detail="Pilot planning data is invalid")
    try:
        original = date.fromisoformat(original_date)
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Pilot planning data is invalid") from error
    if _monday(original) != _monday(payload.lesson_date):
        raise HTTPException(status_code=422, detail="Move the lesson within the same planning week")

    store = SupabaseTeachingAssignmentStore(client, identity.subject)
    try:
        assignment = store.get(identity.subject, assignment_id)
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if assignment is None:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")

    weekday = payload.lesson_date.isoweekday()
    allowed = any(
        weekday in pattern.weekdays
        and pattern.effective_start <= payload.lesson_date <= pattern.effective_end
        for pattern in assignment.meeting_patterns
    )
    if not allowed:
        raise HTTPException(status_code=422, detail="Select a day when this class normally meets")

    try:
        exception_rows = _records(
            client.request(
                "GET",
                "schedule_exceptions",
                params={
                    "teaching_assignment_id": f"eq.{assignment_id}",
                    "exception_date": f"eq.{payload.lesson_date.isoformat()}",
                    "select": "is_available",
                    "limit": "1",
                },
            )
        )
    except SupabaseRestError as error:
        raise HTTPException(status_code=503, detail="Schedule availability could not be verified") from error
    if exception_rows and exception_rows[0].get("is_available") is False:
        raise HTTPException(
            status_code=422,
            detail="That date is unavailable for this class because of the saved schedule exception",
        )

    try:
        updated = _records(
            client.request(
                "PATCH",
                "scheduled_lessons",
                params={"id": f"eq.{scheduled_lesson_id}"},
                payload={
                    "school_date": payload.lesson_date.isoformat(),
                    "is_teacher_override": True,
                },
                prefer="return=representation",
            )
        )
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise HTTPException(status_code=403, detail="Pilot planning access was denied") from error
        raise HTTPException(status_code=409, detail="Planned lesson day could not be changed") from error
    if not updated:
        raise HTTPException(status_code=409, detail="Planned lesson day could not be changed")
    return PlannedLessonMoveRead(
        scheduled_lesson_id=scheduled_lesson_id,
        lesson_date=payload.lesson_date,
    )


@router.post("/{scheduled_lesson_id}/replace")
def replace_planned_lesson(
    scheduled_lesson_id: UUID,
    payload: PlannedLessonReplacement,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Replace curriculum with the next paced lesson or a teacher-authored manual class."""
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    client = SupabaseRestClient.from_settings(settings, access_token=identity.access_token)
    try:
        client.request(
            "POST",
            "rpc/replace_weekly_scheduled_lesson",
            payload={
                "target_scheduled_lesson_id": str(scheduled_lesson_id),
                "replacement_kind": payload.replacement_kind,
                "target_manual_unit_title": payload.manual_unit_title,
                "target_manual_lesson_title": payload.manual_lesson_title,
                "target_manual_learning_targets": payload.manual_learning_targets,
                "target_manual_assessment": payload.manual_assessment,
                "original_disposition": payload.original_disposition,
            },
        )
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise HTTPException(status_code=403, detail="Planned lesson replacement was denied") from error
        if error.status_code in {400, 404, 409, 422}:
            raise HTTPException(
                status_code=409,
                detail="The scheduled lesson could not be replaced. Reopen the current plan and try again.",
            ) from error
        raise HTTPException(status_code=503, detail="Planned lesson replacement is unavailable") from error
    return {"status": "replaced"}
