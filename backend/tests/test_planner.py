from datetime import date, time

from app.fixtures import (
    ASSIGNMENT_IDS,
    afternoon_block_pattern,
    period_pattern,
    synthetic_jrotc_lessons,
)
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


def test_one_pacing_lesson_is_assigned_to_each_class_day() -> None:
    lessons = synthetic_jrotc_lessons("LET 1", count=2)
    plan = build_weekly_plan(
        assignment_id=ASSIGNMENT_IDS["LET 1"],
        week_start=date(2026, 8, 10),
        patterns=[period_pattern()],
        lessons=lessons,
    )

    assert [item.curriculum_lesson_id for item in plan] == [lessons[0].id, lessons[1].id]
    assert [item.date.isoformat() for item in plan] == ["2026-08-10", "2026-08-11"]
    assert [item.planned_minutes for item in plan] == [50, 50]
    assert [item.segment_number for item in plan] == [1, 1]


def test_block_schedule_uses_one_lesson_per_day_regardless_of_saved_minutes() -> None:
    lessons = synthetic_jrotc_lessons("LET 4", count=5)
    for lesson in lessons:
        lesson.estimated_minutes = 530
        lesson.can_split = True
    block_pattern = MeetingPattern(
        schedule_type=ScheduleType.BLOCK,
        weekdays=[1, 2, 3, 4, 5],
        start_time=time(8, 0),
        end_time=time(9, 46),
        effective_start=date(2026, 8, 6),
        effective_end=date(2027, 5, 24),
    )

    plan = build_weekly_plan(
        assignment_id=ASSIGNMENT_IDS["LET 4"],
        week_start=date(2026, 8, 10),
        patterns=[block_pattern],
        lessons=lessons,
    )

    assert [item.curriculum_lesson_id for item in plan] == [lesson.id for lesson in lessons]
    assert [item.date.isoformat() for item in plan] == [
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
        "2026-08-13",
        "2026-08-14",
    ]
    assert [item.planned_minutes for item in plan] == [106, 106, 106, 106, 106]


def test_no_class_exception_skips_date_without_consuming_lesson() -> None:
    lessons = synthetic_jrotc_lessons("LET 1", count=2)
    exception = ScheduleException(
        date=date(2026, 8, 10),
        kind="testing",
        note="State testing",
    )

    plan = build_weekly_plan(
        assignment_id=ASSIGNMENT_IDS["LET 1"],
        week_start=date(2026, 8, 10),
        patterns=[period_pattern()],
        lessons=lessons,
        exceptions=[exception],
    )

    assert [item.curriculum_lesson_id for item in plan] == [lessons[0].id, lessons[1].id]
    assert [item.date.isoformat() for item in plan] == ["2026-08-11", "2026-08-12"]


def test_shortened_class_keeps_one_lesson_on_that_day() -> None:
    lesson = synthetic_jrotc_lessons("LET 1", count=1)[0]
    lesson.estimated_minutes = 530
    exception = ScheduleException(
        date=date(2026, 8, 10),
        kind="shortened_day",
        note="Assembly schedule",
        instructional_minutes=30,
    )

    plan = build_weekly_plan(
        assignment_id=ASSIGNMENT_IDS["LET 1"],
        week_start=date(2026, 8, 10),
        patterns=[period_pattern()],
        lessons=[lesson],
        exceptions=[exception],
    )

    assert len(plan) == 1
    assert plan[0].date.isoformat() == "2026-08-10"
    assert plan[0].planned_minutes == 30
