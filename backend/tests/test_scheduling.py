from datetime import date

from app.scheduling import (
    CarryForwardAction,
    LessonSegment,
    Outcome,
    ValidationResult,
    remaining_queue,
)


def test_missed_carried_lesson_remains_ahead_of_later_work() -> None:
    first = LessonSegment("let1", "lesson-1", 1.0, date(2026, 8, 10), 50)
    second = LessonSegment("let1", "lesson-2", 2.0, date(2026, 8, 11), 50)
    validations = {
        (first.lesson_id, first.planned_date): ValidationResult(
            first, Outcome.MISSED, CarryForwardAction.CARRY_FORWARD
        ),
        (second.lesson_id, second.planned_date): ValidationResult(second, Outcome.COMPLETED),
    }

    assert remaining_queue([first, second], validations) == [first]


def test_completed_and_skipped_lessons_leave_queue() -> None:
    completed = LessonSegment("let1", "lesson-1", 1.0, date(2026, 8, 10), 50)
    skipped = LessonSegment("let1", "lesson-2", 2.0, date(2026, 8, 11), 50)
    validations = {
        (completed.lesson_id, completed.planned_date): ValidationResult(
            completed, Outcome.COMPLETED
        ),
        (skipped.lesson_id, skipped.planned_date): ValidationResult(
            skipped, Outcome.MISSED, CarryForwardAction.SKIP
        ),
    }

    assert remaining_queue([completed, skipped], validations) == []


def test_assignments_are_not_mixed_by_caller_contract() -> None:
    let1 = LessonSegment("let1", "lesson-1", 1.0, date(2026, 8, 10), 50)
    let2 = LessonSegment("let2", "lesson-1", 1.0, date(2026, 8, 10), 90)

    assert remaining_queue([let1], {}) == [let1]
    assert remaining_queue([let2], {}) == [let2]
