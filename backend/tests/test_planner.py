from datetime import date, time
from uuid import UUID

from app.fixtures import ASSIGNMENT_IDS, afternoon_block_pattern, period_pattern, synthetic_jrotc_lessons
from app.models import MeetingPattern, ScheduleException, ScheduleType
from app.planner import available_minutes_for_date, build_weekly_plan


def test_period_and_block_patterns_have_different_capacity() -> None:
    monday = date(2026, 8, 10)
    assert available_minutes_for_date(monday, [period_pattern()], []) == 50
    assert available_minutes_for_date(monday, [afternoon_block_pattern()], []) == 90


def test_exception_removes_instructional_minutes() -> None:
    monday = date(2026, 8, 10)
    exception = ScheduleException(date=monday, kind="testing", note="State testing")
    assert available_minutes_for_date(monday, [period_pattern()], [exception]) == 0


def test_weekly_plan_splits_long_lesson_without_reordering() -> None:
    lessons = synthetic_jrotc_lessons("LET 1", count=2)
    lessons[0].estimated_minutes = 75
    plan = build_weekly_plan(
        assignment_id=ASSIGNMENT_IDS["LET 1"],
        week_start=date(2026, 8, 10),
        patterns=[period_pattern()],
        lessons=lessons,
    )
    assert [item.curriculum_lesson_id for item in plan[:2]] == [lessons[0].id, lessons[0].id]
    assert [item.planned_minutes for item in plan[:2]] == [50, 25]
    assert plan[2].curriculum_lesson_id == lessons[1].id


def test_unsplittable_lesson_waits_for_sufficient_block() -> None:
    lesson = synthetic_jrotc_lessons("LET 4", count=1)[0]
    lesson.estimated_minutes = 80
    lesson.can_split = False
    short_pattern = MeetingPattern(
        schedule_type=ScheduleType.PERIOD,
        weekdays=[1, 2, 3, 4, 5],
        start_time=time(8, 0),
        end_time=time(8, 50),
        effective_start=date(2026, 8, 6),
        effective_end=date(2027, 5, 24),
    )
    plan = build_weekly_plan(
        assignment_id=UUID("00000000-0000-0000-0000-000000001004"),
        week_start=date(2026, 8, 10),
        patterns=[short_pattern],
        lessons=[lesson],
    )
    assert plan == []
