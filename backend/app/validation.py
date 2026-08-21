from dataclasses import dataclass
from datetime import date
from uuid import UUID

from .models import LessonStatus, ValidationUpdate


@dataclass(frozen=True, slots=True)
class ScheduledLessonRecord:
    id: UUID
    assignment_id: UUID
    curriculum_lesson_id: UUID | None
    date: date
    sequence: int
    status: LessonStatus = LessonStatus.PLANNED


@dataclass(frozen=True, slots=True)
class ValidatedLessonRecord:
    scheduled_lesson_id: UUID
    assignment_id: UUID
    curriculum_lesson_id: UUID | None
    date: date
    sequence: int
    status: LessonStatus
    reason: str | None
    teacher_note: str | None
    carry_forward: bool


@dataclass(frozen=True, slots=True)
class FridayValidationResult:
    validated: tuple[ValidatedLessonRecord, ...]
    carry_forward_curriculum_lesson_ids: tuple[UUID, ...]
    completed_count: int
    modified_count: int
    missed_count: int
    skipped_count: int


def apply_friday_validation(
    scheduled: list[ScheduledLessonRecord],
    updates: dict[UUID, ValidationUpdate],
) -> FridayValidationResult:
    missing_updates = sorted(str(item.id) for item in scheduled if item.id not in updates)
    if missing_updates:
        missing = ", ".join(missing_updates)
        raise ValueError(f"Every scheduled lesson requires validation: {missing}")

    validated: list[ValidatedLessonRecord] = []
    for item in sorted(scheduled, key=lambda record: (record.date, record.sequence)):
        update = updates[item.id]
        validated.append(
            ValidatedLessonRecord(
                scheduled_lesson_id=item.id,
                assignment_id=item.assignment_id,
                curriculum_lesson_id=item.curriculum_lesson_id,
                date=item.date,
                sequence=item.sequence,
                status=update.status,
                reason=update.reason,
                teacher_note=update.teacher_note,
                carry_forward=update.carry_forward,
            )
        )

    carry_forward_ids = tuple(
        record.curriculum_lesson_id
        for record in validated
        if record.curriculum_lesson_id is not None
        and (record.carry_forward or record.status == LessonStatus.MISSED)
    )

    return FridayValidationResult(
        validated=tuple(validated),
        carry_forward_curriculum_lesson_ids=carry_forward_ids,
        completed_count=sum(record.status == LessonStatus.COMPLETED for record in validated),
        modified_count=sum(record.status == LessonStatus.MODIFIED for record in validated),
        missed_count=sum(record.status == LessonStatus.MISSED for record in validated),
        skipped_count=sum(record.status == LessonStatus.SKIPPED for record in validated),
    )
