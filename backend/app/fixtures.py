from __future__ import annotations

from datetime import date, time
from uuid import UUID

from .models import CurriculumLesson, MeetingPattern, ScheduleException, ScheduleType

SYNTHETIC_TEACHER_ID = UUID("00000000-0000-0000-0000-000000000101")
SYNTHETIC_SCHOOL_ID = UUID("00000000-0000-0000-0000-000000000201")

ASSIGNMENT_IDS = {
    "LET 1": UUID("00000000-0000-0000-0000-000000001001"),
    "LET 2": UUID("00000000-0000-0000-0000-000000001002"),
    "LET 3": UUID("00000000-0000-0000-0000-000000001003"),
    "LET 4": UUID("00000000-0000-0000-0000-000000001004"),
}
CURRICULUM_IDS = {
    name: UUID(f"00000000-0000-0000-0000-{index:012d}")
    for index, name in enumerate(ASSIGNMENT_IDS, start=2001)
}


def period_pattern() -> MeetingPattern:
    return MeetingPattern(
        schedule_type=ScheduleType.PERIOD,
        weekdays=[1, 2, 3, 4, 5],
        start_time=time(8, 0),
        end_time=time(8, 50),
        effective_start=date(2026, 8, 6),
        effective_end=date(2027, 5, 24),
    )


def afternoon_block_pattern() -> MeetingPattern:
    return MeetingPattern(
        schedule_type=ScheduleType.BLOCK,
        weekdays=[1, 2, 3, 4, 5],
        start_time=time(13, 5),
        end_time=time(14, 35),
        effective_start=date(2026, 8, 6),
        effective_end=date(2027, 5, 24),
    )


def anniston_exceptions() -> list[ScheduleException]:
    return [
        ScheduleException(date=date(2026, 9, 7), kind="holiday", note="Labor Day"),
        ScheduleException(date=date(2026, 10, 13), kind="other", note="E-Learning / staff PD"),
        ScheduleException(date=date(2026, 11, 11), kind="holiday", note="Veterans Day"),
        ScheduleException(date=date(2027, 1, 18), kind="holiday", note="MLK Jr. Day"),
        ScheduleException(date=date(2027, 2, 12), kind="other", note="E-Learning / staff PD"),
        ScheduleException(date=date(2027, 4, 26), kind="other", note="E-Learning / staff PD"),
    ]


def synthetic_jrotc_lessons(level: str, count: int = 12) -> list[CurriculumLesson]:
    curriculum_id = CURRICULUM_IDS[level]
    focuses = [
        "Program orientation and expectations",
        "Customs, courtesies, and the Cadet Creed",
        "Leadership and followership",
        "Uniform standards and accountability",
        "Stationary drill fundamentals",
        "Marching and formation movement",
        "Physical readiness and goal setting",
        "Communication and team development",
        "Citizenship and service learning",
        "First aid and risk management",
        "Map reading and land navigation",
        "Assessment, reflection, and recovery",
    ]
    lessons: list[CurriculumLesson] = []
    for sequence, focus in enumerate(focuses[:count], start=1):
        lessons.append(
            CurriculumLesson(
                id=UUID(f"00000000-0000-0000-{int(level[-1]):04d}-{sequence:012d}"),
                curriculum_id=curriculum_id,
                sequence=sequence,
                unit_title=f"{level} Unit {(sequence - 1) // 3 + 1}",
                lesson_title=focus,
                estimated_minutes=50 if level != "LET 4" else 90,
                standards=[f"Army JROTC {level} competency {sequence}"],
                learning_target=f"Cadets will demonstrate understanding of {focus.lower()}.",
                know=["Required terminology", "Safety and accountability expectations"],
                understand=["How the lesson supports leadership and citizenship development"],
                do=["Apply the lesson in a guided or practical activity"],
                assessment="Teacher observation, exit ticket, or practical check",
                resources=["Army JROTC curriculum materials", "Instructor-prepared resources"],
            )
        )
    return lessons
