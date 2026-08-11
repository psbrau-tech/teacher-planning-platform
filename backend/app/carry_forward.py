from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

from .models import CurriculumLesson
from .validation import FridayValidationResult


def lessons_for_next_week(
    lessons: list[CurriculumLesson],
    validation: FridayValidationResult | None,
) -> list[CurriculumLesson]:
    """Build the next curriculum queue from one Friday validation.

    Retained for the deterministic carry-forward unit contract. Live planning uses
    ``lessons_for_planning_history`` so a class never forgets progress older than
    the immediately preceding week.
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


def lessons_for_planning_history(
    lessons: list[CurriculumLesson],
    *,
    validations: Sequence[tuple[date, FridayValidationResult]],
    scheduled_history: Sequence[tuple[int, date]],
    target_week_start: date,
) -> list[CurriculumLesson]:
    """Return the class-specific queue for a Monday-starting planning week.

    ``scheduled_history`` is assignment-scoped. Its highest sequence is the
    class's provisional progress cursor, which prevents an early-built future
    week from rescheduling lessons already placed in an earlier week. Friday
    validation can explicitly carry a sequence back in front of that cursor.

    Carry-forward state is cumulative. A carried lesson stops being carried
    automatically once that same sequence has been scheduled again after the
    validation that requested the carry; a later Friday validation can carry it
    again if the teacher chooses to do so.

    Sequence positions deliberately survive curriculum copies/revisions. That
    lets two classes share a curriculum while maintaining independent progress,
    and lets one class fork the curriculum mid-year without old lessons
    reappearing.
    """
    ordered = sorted(lessons, key=lambda lesson: lesson.sequence)
    if not ordered:
        return []

    history = [
        (sequence, school_date)
        for sequence, school_date in scheduled_history
        if school_date < target_week_start
    ]
    cursor = max((sequence for sequence, _school_date in history), default=0)

    latest_validation: dict[int, tuple[date, bool]] = {}
    for week_start, result in sorted(validations, key=lambda item: item[0]):
        if week_start >= target_week_start:
            continue
        for record in result.validated:
            latest_validation[record.sequence] = (week_start, record.carry_forward)

    carry_sequences: list[int] = []
    for sequence, (validation_week, should_carry) in latest_validation.items():
        if not should_carry:
            continue
        validation_week_end = validation_week + timedelta(days=4)
        scheduled_again = any(
            scheduled_sequence == sequence
            and validation_week_end < school_date < target_week_start
            for scheduled_sequence, school_date in history
        )
        if not scheduled_again:
            carry_sequences.append(sequence)

    by_sequence = {lesson.sequence: lesson for lesson in ordered}
    carry = [
        by_sequence[sequence]
        for sequence in sorted(set(carry_sequences))
        if sequence in by_sequence
    ]
    carry_set = set(carry_sequences)
    future = [
        lesson
        for lesson in ordered
        if lesson.sequence > cursor and lesson.sequence not in carry_set
    ]
    return carry + future
