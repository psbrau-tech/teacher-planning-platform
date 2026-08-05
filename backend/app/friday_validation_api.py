from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_teacher
from .friday_validation_store import (
    FridayValidationRecord,
    friday_validation_store,
)
from .models import LessonStatus, ValidationUpdate
from .validation import ScheduledLessonRecord, apply_friday_validation

router = APIRouter(prefix="/api/v1/friday-validations", tags=["planning"])


class FridayLessonValidationWrite(BaseModel):
    scheduled_lesson_id: UUID
    curriculum_lesson_id: UUID
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
    curriculum_lesson_id: UUID
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


@router.get("", response_model=FridayValidationRead)
def get_friday_validation(
    assignment_id: UUID,
    week_start: date,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
) -> FridayValidationRead:
    record = friday_validation_store.get(teacher.subject, assignment_id, week_start)
    if record is None:
        raise HTTPException(status_code=404, detail="Friday validation not found")
    return _to_read_model(record)


@router.put("", response_model=FridayValidationRead)
def save_friday_validation(
    payload: FridayValidationWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
) -> FridayValidationRead:
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
        result = apply_friday_validation(scheduled, updates)
        record = friday_validation_store.save(
            teacher_id=teacher.subject,
            assignment_id=payload.assignment_id,
            week_start=payload.week_start,
            result=result,
            expected_revision=payload.expected_revision,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _to_read_model(record)
