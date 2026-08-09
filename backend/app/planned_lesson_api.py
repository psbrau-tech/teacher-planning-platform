from datetime import date, timedelta
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings
from .supabase_persistence import PersistenceError, SupabaseTeachingAssignmentStore
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/plans/lessons", tags=["planning"])


class PlannedLessonMove(BaseModel):
    lesson_date: date


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Pilot planning data is unavailable")
    return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


@router.patch("/{scheduled_lesson_id}", status_code=204)
def move_planned_lesson(
    scheduled_lesson_id: UUID,
    payload: PlannedLessonMove,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Move one scheduled lesson to another valid meeting day in the same week."""
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
    return Response(status_code=204)