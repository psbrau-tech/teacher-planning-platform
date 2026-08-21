from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_teacher
from .friday_validation_store import (
    FridayValidationRecord,
    FridayValidationStore,
    friday_validation_store,
)
from .models import LessonStatus, ValidationUpdate
from .settings import Settings, get_settings
from .supabase_persistence import PersistenceError, SupabaseFridayValidationStore
from .supabase_rest import SupabaseRestClient
from .validation import ScheduledLessonRecord, apply_friday_validation
from .week_dates import require_monday

router = APIRouter(prefix="/api/v1/friday-validations", tags=["planning"])


class FridayLessonValidationWrite(BaseModel):
    scheduled_lesson_id: UUID
    curriculum_lesson_id: UUID | None
    lesson_date: date
    sequence: int = Field(ge=1)
    status: LessonStatus
    reason: str | None = None
    teacher_note: str | None = None
    carry_forward: bool = False


class FridayValidationWrite(BaseModel):
    assignment_id: UUID
    week_start: date
    lessons: list[FridayLessonValidationWrite] = Field(min_length=1)
    expected_revision: int | None = Field(default=None, ge=0)


class FridayLessonValidationRead(BaseModel):
    scheduled_lesson_id: UUID
    curriculum_lesson_id: UUID | None
    lesson_date: date
    sequence: int
    status: LessonStatus
    reason: str | None
    teacher_note: str | None
    carry_forward: bool


class FridayValidationRead(BaseModel):
    teacher_id: str
    assignment_id: UUID
    week_start: date
    revision: int
    validated_at: str
    completed_count: int
    modified_count: int
    missed_count: int
    skipped_count: int
    carry_forward_curriculum_lesson_ids: list[UUID]
    lessons: list[FridayLessonValidationRead]


def _to_read_model(record: FridayValidationRecord) -> FridayValidationRead:
    return FridayValidationRead(
        teacher_id=record.teacher_id,
        assignment_id=record.assignment_id,
        week_start=record.week_start,
        revision=record.revision,
        validated_at=record.validated_at.isoformat(),
        completed_count=record.result.completed_count,
        modified_count=record.result.modified_count,
        missed_count=record.result.missed_count,
        skipped_count=record.result.skipped_count,
        carry_forward_curriculum_lesson_ids=list(
            record.result.carry_forward_curriculum_lesson_ids
        ),
        lessons=[
            FridayLessonValidationRead(
                scheduled_lesson_id=item.scheduled_lesson_id,
                curriculum_lesson_id=item.curriculum_lesson_id,
                lesson_date=item.date,
                sequence=item.sequence,
                status=item.status,
                reason=item.reason,
                teacher_note=item.teacher_note,
                carry_forward=item.carry_forward,
            )
            for item in record.result.validated
        ],
    )


def _store_for(
    teacher: AuthenticatedTeacher,
    settings: Settings,
) -> FridayValidationStore | SupabaseFridayValidationStore:
    if teacher.access_token is None:
        return friday_validation_store
    return SupabaseFridayValidationStore(
        client=SupabaseRestClient.from_settings(
            settings,
            access_token=teacher.access_token,
        ),
        authenticated_teacher_id=teacher.subject,
    )


@router.get("", response_model=FridayValidationRead)
def get_friday_validation(
    assignment_id: UUID,
    week_start: date,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FridayValidationRead:
    require_monday(week_start)
    try:
        record = _store_for(teacher, settings).get(
            teacher.subject,
            assignment_id,
            week_start,
        )
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if record is None:
        raise HTTPException(status_code=404, detail="Friday validation not found")
    return _to_read_model(record)


@router.put("", response_model=FridayValidationRead)
def save_friday_validation(
    payload: FridayValidationWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FridayValidationRead:
    require_monday(payload.week_start)
    scheduled = [
        ScheduledLessonRecord(
            id=item.scheduled_lesson_id,
            assignment_id=payload.assignment_id,
            curriculum_lesson_id=item.curriculum_lesson_id,
            date=item.lesson_date,
            sequence=item.sequence,
        )
        for item in payload.lessons
    ]
    updates = {
        item.scheduled_lesson_id: ValidationUpdate(
            status=item.status,
            reason=item.reason,
            teacher_note=item.teacher_note,
            carry_forward=item.carry_forward,
        )
        for item in payload.lessons
    }
    try:
        store = _store_for(teacher, settings)
        current = store.get(
            teacher.subject,
            payload.assignment_id,
            payload.week_start,
        )
        if current is not None and payload.expected_revision is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Friday validation revision conflict: reload the saved validation "
                    "before updating it"
                ),
            )

        result = apply_friday_validation(scheduled, updates)
        record = store.save(
            teacher_id=teacher.subject,
            assignment_id=payload.assignment_id,
            week_start=payload.week_start,
            result=result,
            expected_revision=payload.expected_revision,
        )
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _to_read_model(record)
