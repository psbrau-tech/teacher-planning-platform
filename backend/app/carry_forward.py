from .models import CurriculumLesson
from .validation import FridayValidationResult


def lessons_for_next_week(
    lessons: list[CurriculumLesson],
    validation: FridayValidationResult | None,
) -> list[CurriculumLesson]:
    """Build the next curriculum queue from Friday validation.

    Carry-forward lessons remain in their validated order and are placed before
    untouched future lessons. Lessons already validated without carry-forward
    are removed from the next-week queue.
    """
    ordered = sorted(lessons, key=lambda lesson: lesson.sequence)
    if validation is None:
        return ordered

    by_id = {lesson.id: lesson for lesson in ordered}
    validated_ids = {record.curriculum_lesson_id for record in validation.validated}

    carry_forward: list[CurriculumLesson] = []
    seen: set[object] = set()
    for lesson_id in validation.carry_forward_curriculum_lesson_ids:
        lesson = by_id.get(lesson_id)
        if lesson is not None and lesson_id not in seen:
            carry_forward.append(lesson)
            seen.add(lesson_id)

    future = [lesson for lesson in ordered if lesson.id not in validated_ids]
    return carry_forward + future
