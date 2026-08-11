from datetime import date
from uuid import UUID, uuid4

from app.carry_forward import lessons_for_planning_history
from app.models import CurriculumLesson, LessonStatus
from app.validation import FridayValidationResult, ValidatedLessonRecord


def _lesson(sequence: int) -> CurriculumLesson:
    return CurriculumLesson(
        id=uuid4(),
        curriculum_id=uuid4(),
        sequence=sequence,
        unit_title="Unit",
        lesson_title=f"Lesson {sequence}",
        learning_target="",
    )


def _validation(
    *,
    assignment_id: UUID,
    lesson: CurriculumLesson,
    week_start: date,
    carry_forward: bool,
) -> FridayValidationResult:
    record = ValidatedLessonRecord(
        scheduled_lesson_id=uuid4(),
        assignment_id=assignment_id,
        curriculum_lesson_id=lesson.id,
        date=week_start,
        sequence=lesson.sequence,
        status=LessonStatus.MISSED if carry_forward else LessonStatus.COMPLETED,
        reason="Schedule change" if carry_forward else None,
        teacher_note=None,
        carry_forward=carry_forward,
    )
    return FridayValidationResult(
        validated=(record,),
        carry_forward_curriculum_lesson_ids=(lesson.id,) if carry_forward else (),
        completed_count=0 if carry_forward else 1,
        modified_count=0,
        missed_count=1 if carry_forward else 0,
        skipped_count=0,
    )


def test_progress_uses_full_assignment_history_and_keeps_carry_forward_first() -> None:
    lessons = [_lesson(sequence) for sequence in range(1, 7)]
    assignment_id = uuid4()
    validation = _validation(
        assignment_id=assignment_id,
        lesson=lessons[1],
        week_start=date(2026, 8, 3),
        carry_forward=True,
    )

    queue = lessons_for_planning_history(
        lessons,
        validations=[(date(2026, 8, 3), validation)],
        scheduled_history=[
            (1, date(2026, 8, 3)),
            (2, date(2026, 8, 4)),
            (3, date(2026, 8, 5)),
        ],
        target_week_start=date(2026, 8, 10),
    )

    assert [lesson.sequence for lesson in queue] == [2, 4, 5, 6]


def test_carried_lesson_does_not_duplicate_after_it_is_scheduled_again() -> None:
    lessons = [_lesson(sequence) for sequence in range(1, 7)]
    assignment_id = uuid4()
    validation = _validation(
        assignment_id=assignment_id,
        lesson=lessons[1],
        week_start=date(2026, 8, 3),
        carry_forward=True,
    )

    queue = lessons_for_planning_history(
        lessons,
        validations=[(date(2026, 8, 3), validation)],
        scheduled_history=[
            (1, date(2026, 8, 3)),
            (2, date(2026, 8, 4)),
            (3, date(2026, 8, 5)),
            (2, date(2026, 8, 10)),
            (4, date(2026, 8, 11)),
        ],
        target_week_start=date(2026, 8, 17),
    )

    assert [lesson.sequence for lesson in queue] == [5, 6]


def test_two_classes_sharing_curriculum_keep_independent_progress() -> None:
    lessons = [_lesson(sequence) for sequence in range(1, 7)]

    class_a = lessons_for_planning_history(
        lessons,
        validations=[],
        scheduled_history=[
            (1, date(2026, 8, 3)),
            (2, date(2026, 8, 4)),
        ],
        target_week_start=date(2026, 8, 10),
    )
    class_b = lessons_for_planning_history(
        lessons,
        validations=[],
        scheduled_history=[
            (1, date(2026, 8, 3)),
            (2, date(2026, 8, 4)),
            (3, date(2026, 8, 5)),
            (4, date(2026, 8, 6)),
        ],
        target_week_start=date(2026, 8, 10),
    )

    assert [lesson.sequence for lesson in class_a] == [3, 4, 5, 6]
    assert [lesson.sequence for lesson in class_b] == [5, 6]


def test_curriculum_copy_with_new_lesson_ids_preserves_sequence_progress() -> None:
    original = [_lesson(sequence) for sequence in range(1, 6)]
    revised_copy = [_lesson(sequence) for sequence in range(1, 7)]
    assert {lesson.id for lesson in original}.isdisjoint({lesson.id for lesson in revised_copy})

    queue = lessons_for_planning_history(
        revised_copy,
        validations=[],
        scheduled_history=[
            (1, date(2026, 8, 3)),
            (2, date(2026, 8, 4)),
            (3, date(2026, 8, 5)),
        ],
        target_week_start=date(2026, 8, 10),
    )

    assert [lesson.sequence for lesson in queue] == [4, 5, 6]
