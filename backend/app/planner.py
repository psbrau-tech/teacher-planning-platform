from collections.abc import Iterable
from datetime import date, timedelta
from uuid import UUID

from .models import CurriculumLesson, MeetingPattern, PlannedLesson, ScheduleException


def iter_week_dates(week_start: date) -> Iterable[date]:
    if week_start.isoweekday() != 1:
        raise ValueError("week_start must be a Monday")
    for offset in range(5):
        yield week_start + timedelta(days=offset)


def meeting_minutes(pattern: MeetingPattern) -> int:
    start = pattern.start_time.hour * 60 + pattern.start_time.minute
    end = pattern.end_time.hour * 60 + pattern.end_time.minute
    return end - start


def available_minutes_for_date(
    day: date,
    patterns: list[MeetingPattern],
    exceptions: list[ScheduleException],
) -> int:
    matching = [
        pattern
        for pattern in patterns
        if pattern.effective_start <= day <= pattern.effective_end
        and day.isoweekday() in pattern.weekdays
    ]
    if not matching:
        return 0

    assignment_exception = next((item for item in exceptions if item.date == day), None)
    if assignment_exception:
        return assignment_exception.instructional_minutes

    return sum(meeting_minutes(pattern) for pattern in matching)


def build_weekly_plan(
    *,
    assignment_id: UUID,
    week_start: date,
    patterns: list[MeetingPattern],
    lessons: list[CurriculumLesson],
    exceptions: list[ScheduleException] | None = None,
) -> list[PlannedLesson]:
    """Assign curriculum lessons to instructional dates without reordering them.

    Normal lessons are atomic: a few unused minutes at the end of a class period do
    not start the next lesson and create an artificial one-minute segment. A lesson
    with an explicit duration may still span multiple meetings when its duration is
    longer than a full available meeting and ``can_split`` permits continuation.
    """
    exceptions = exceptions or []
    ordered_lessons = sorted(lessons, key=lambda lesson: lesson.sequence)
    lesson_index = 0
    remaining_minutes = (
        ordered_lessons[0].estimated_minutes if ordered_lessons else None
    )
    segment_number = 1
    planned: list[PlannedLesson] = []

    for day in iter_week_dates(week_start):
        available = available_minutes_for_date(day, patterns, exceptions)
        day_capacity = available
        while available > 0 and lesson_index < len(ordered_lessons):
            lesson = ordered_lessons[lesson_index]

            if remaining_minutes is None:
                planned.append(
                    PlannedLesson(
                        assignment_id=assignment_id,
                        curriculum_lesson_id=lesson.id,
                        date=day,
                        planned_minutes=available,
                        segment_number=1,
                    )
                )
                available = 0
                lesson_index += 1
                segment_number = 1
                if lesson_index < len(ordered_lessons):
                    remaining_minutes = ordered_lessons[lesson_index].estimated_minutes
                continue

            # Do not use a small remainder from a previous lesson to begin the next
            # lesson. This prevents accidental 1-minute/49-minute segmentation when
            # a 50-minute lesson is placed in a 51-minute class period.
            if available < remaining_minutes and available < day_capacity:
                break

            if not lesson.can_split and available < remaining_minutes:
                break

            allocated = min(available, remaining_minutes)
            planned.append(
                PlannedLesson(
                    assignment_id=assignment_id,
                    curriculum_lesson_id=lesson.id,
                    date=day,
                    planned_minutes=allocated,
                    segment_number=segment_number,
                )
            )
            available -= allocated
            remaining_minutes -= allocated

            if remaining_minutes == 0:
                lesson_index += 1
                segment_number = 1
                if lesson_index < len(ordered_lessons):
                    remaining_minutes = ordered_lessons[lesson_index].estimated_minutes
            else:
                segment_number += 1
                break

    return planned
