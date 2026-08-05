from datetime import date
from uuid import UUID

import pytest

from app.friday_validation_store import FridayValidationStore
from app.models import LessonStatus, ValidationUpdate
from app.validation import (
    FridayValidationResult,
    ScheduledLessonRecord,
    apply_friday_validation,
)

ASSIGNMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SCHEDULED_ID = UUID("22222222-2222-2222-2222-222222222222")
LESSON_ID = UUID("33333333-3333-3333-3333-333333333333")
WEEK_START = date(2026, 8, 10)


def result_with(status: LessonStatus = LessonStatus.COMPLETED) -> FridayValidationResult:
    scheduled = [
        ScheduledLessonRecord(
            id=SCHEDULED_ID,
            assignment_id=ASSIGNMENT_ID,
            curriculum_lesson_id=LESSON_ID,
            date=WEEK_START,
            sequence=1,
        )
    ]
    return apply_friday_validation(
        scheduled,
        {
            SCHEDULED_ID: ValidationUpdate(
                status=status,
                reason="Testing schedule" if status == LessonStatus.MISSED else None,
                carry_forward=status == LessonStatus.MISSED,
            )
        },
    )


def test_validation_can_be_saved_and_reloaded() -> None:
    store = FridayValidationStore()
    saved = store.save(
        teacher_id="teacher-a",
        assignment_id=ASSIGNMENT_ID,
        week_start=WEEK_START,
        result=result_with(),
    )

    assert saved.revision == 1
    assert saved.result.completed_count == 1
    assert store.get("teacher-a", ASSIGNMENT_ID, WEEK_START) == saved


def test_validation_update_requires_current_revision() -> None:
    store = FridayValidationStore()
    first = store.save(
        teacher_id="teacher-a",
        assignment_id=ASSIGNMENT_ID,
        week_start=WEEK_START,
        result=result_with(),
    )
    second = store.save(
        teacher_id="teacher-a",
        assignment_id=ASSIGNMENT_ID,
        week_start=WEEK_START,
        result=result_with(LessonStatus.MISSED),
        expected_revision=first.revision,
    )

    assert second.revision == 2
    assert second.result.missed_count == 1
    assert second.result.carry_forward_curriculum_lesson_ids == (LESSON_ID,)

    with pytest.raises(ValueError, match="revision conflict"):
        store.save(
            teacher_id="teacher-a",
            assignment_id=ASSIGNMENT_ID,
            week_start=WEEK_START,
            result=result_with(),
            expected_revision=first.revision,
        )


def test_validation_is_isolated_by_teacher_assignment_and_week() -> None:
    store = FridayValidationStore()
    store.save(
        teacher_id="teacher-a",
        assignment_id=ASSIGNMENT_ID,
        week_start=WEEK_START,
        result=result_with(),
    )

    assert store.get("teacher-b", ASSIGNMENT_ID, WEEK_START) is None
    assert store.get(
        "teacher-a",
        UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        WEEK_START,
    ) is None
    assert store.get("teacher-a", ASSIGNMENT_ID, date(2026, 8, 17)) is None
