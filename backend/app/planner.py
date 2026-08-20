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
    """Assign one curriculum lesson to each instructional class day.

    Pacing rows are day-sized instructional units. Saved lesson-minute estimates are
    retained for backward-compatible reads but never split, repeat, or combine pacing
    lessons. A no-class exception skips the date without consuming a lesson; a reduced
    instructional-minutes exception keeps the lesson on that date with the reduced time.
    """
    exceptions = exceptions or []
    ordered_lessons = sorted(lessons, key=lambda lesson: lesson.sequence)
    planned: list[PlannedLesson] = []

    for day in iter_week_dates(week_start):
        if len(planned) >= len(ordered_lessons):
            break
        available = available_minutes_for_date(day, patterns, exceptions)
        if available <= 0:
            continue
        lesson = ordered_lessons[len(planned)]
        planned.append(
            PlannedLesson(
                assignment_id=assignment_id,
                curriculum_lesson_id=lesson.id,
                date=day,
                planned_minutes=available,
                segment_number=1,
            )
        )

    return planned
