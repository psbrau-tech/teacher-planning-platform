from datetime import date
from uuid import UUID

import pytest

from app.models import LessonStatus, ValidationUpdate
from app.validation import ScheduledLessonRecord, apply_friday_validation

ASSIGNMENT_ID = UUID("00000000-0000-0000-0000-000000000101")
LESSON_ONE = UUID("00000000-0000-0000-0000-000000000201")
LESSON_TWO = UUID("00000000-0000-0000-0000-000000000202")
SCHEDULED_ONE = UUID("00000000-0000-0000-0000-000000000301")
SCHEDULED_TWO = UUID("00000000-0000-0000-0000-000000000302")


def scheduled_lessons() -> list[ScheduledLessonRecord]:
    return [
        ScheduledLessonRecord(
            id=SCHEDULED_ONE,
            assignment_id=ASSIGNMENT_ID,
            curriculum_lesson_id=LESSON_ONE,
            date=date(2026, 8, 10),
            sequence=1,
        ),
        ScheduledLessonRecord(
            id=SCHEDULED_TWO,
            assignment_id=ASSIGNMENT_ID,
            curriculum_lesson_id=LESSON_TWO,
            date=date(2026, 8, 11),
            sequence=2,
        ),
    ]


def test_friday_validation_returns_ordered_carry_forward_queue() -> None:
    result = apply_friday_validation(
        scheduled_lessons(),
        {
            SCHEDULED_ONE: ValidationUpdate(status=LessonStatus.COMPLETED),
            SCHEDULED_TWO: ValidationUpdate(
                status=LessonStatus.MISSED,
                reason="Testing",
                carry_forward=True,
            ),
        },
    )

    assert result.completed_count == 1
    assert result.missed_count == 1
    assert result.carry_forward_curriculum_lesson_ids == (LESSON_TWO,)


def test_every_scheduled_lesson_requires_teacher_validation() -> None:
    with pytest.raises(ValueError, match="Every scheduled lesson requires validation"):
        apply_friday_validation(
            scheduled_lessons(),
            {SCHEDULED_ONE: ValidationUpdate(status=LessonStatus.COMPLETED)},
        )


def test_modified_lesson_can_be_taught_without_carry_forward() -> None:
    result = apply_friday_validation(
        scheduled_lessons(),
        {
            SCHEDULED_ONE: ValidationUpdate(
                status=LessonStatus.MODIFIED,
                teacher_note="Compressed for shortened period",
            ),
            SCHEDULED_TWO: ValidationUpdate(status=LessonStatus.COMPLETED),
        },
    )

    assert result.modified_count == 1
    assert result.carry_forward_curriculum_lesson_ids == ()
