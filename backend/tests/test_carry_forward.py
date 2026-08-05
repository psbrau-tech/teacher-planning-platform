from datetime import date
from uuid import UUID

from app.carry_forward import lessons_for_next_week
from app.fixtures import ASSIGNMENT_IDS, synthetic_jrotc_lessons
from app.models import LessonStatus, ValidationUpdate
from app.validation import ScheduledLessonRecord, apply_friday_validation


def _scheduled(lesson_id: UUID, sequence: int) -> ScheduledLessonRecord:
    return ScheduledLessonRecord(
        id=UUID(f"10000000-0000-0000-0000-{sequence:012d}"),
        assignment_id=ASSIGNMENT_IDS["LET 1"],
        curriculum_lesson_id=lesson_id,
        date=date(2026, 8, 10 + sequence),
        sequence=sequence,
    )


def test_without_validation_preserves_curriculum_order() -> None:
    lessons = synthetic_jrotc_lessons("LET 1", count=4)

    result = lessons_for_next_week(list(reversed(lessons)), None)

    assert [lesson.sequence for lesson in result] == [1, 2, 3, 4]


def test_missed_lesson_moves_before_untouched_future_lessons() -> None:
    lessons = synthetic_jrotc_lessons("LET 1", count=5)
    scheduled = [_scheduled(lessons[index].id, index + 1) for index in range(3)]
    validation = apply_friday_validation(
        scheduled,
        {
            scheduled[0].id: ValidationUpdate(status=LessonStatus.COMPLETED),
            scheduled[1].id: ValidationUpdate(
                status=LessonStatus.MISSED,
                reason="School rally",
            ),
            scheduled[2].id: ValidationUpdate(status=LessonStatus.COMPLETED),
        },
    )

    result = lessons_for_next_week(lessons, validation)

    assert [lesson.sequence for lesson in result] == [2, 4, 5]


def test_explicit_modified_carry_forward_is_preserved_once() -> None:
    lessons = synthetic_jrotc_lessons("LET 1", count=4)
    scheduled = [
        _scheduled(lessons[0].id, 1),
        _scheduled(lessons[0].id, 2),
        _scheduled(lessons[1].id, 3),
    ]
    validation = apply_friday_validation(
        scheduled,
        {
            scheduled[0].id: ValidationUpdate(
                status=LessonStatus.MODIFIED,
                carry_forward=True,
            ),
            scheduled[1].id: ValidationUpdate(
                status=LessonStatus.MODIFIED,
                carry_forward=True,
            ),
            scheduled[2].id: ValidationUpdate(status=LessonStatus.COMPLETED),
        },
    )

    result = lessons_for_next_week(lessons, validation)

    assert [lesson.sequence for lesson in result] == [1, 3, 4]
