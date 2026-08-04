from __future__ import annotations

from dataclasses import dataclass


WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")
DAILY_GROUPS = ("clt", "rrt", "cfu", "ri", "sic", "esl")
REFLECTION_FIELDS = tuple(f"reflect_{index}" for index in range(1, 13))

PAGE_ONE_FIELDS = (
    "teacher",
    "course",
    "grade",
    "week_of",
    "unit_topic",
    "standards",
    "know",
    "understand",
    "do",
    "proficiency_scale",
    "common_misconceptions",
    "formative_assessment",
    "summative_assessment",
    "performance_task",
    "resources_materials_links",
)

DAILY_FIELDS = tuple(f"{group}_{day}" for day in WEEKDAYS for group in DAILY_GROUPS)
ALL_HQI_FIELDS = PAGE_ONE_FIELDS + DAILY_FIELDS + REFLECTION_FIELDS


@dataclass(frozen=True, slots=True)
class DailyPlanContent:
    clear_learning_target: str
    rigorous_relevant_task: str
    check_for_understanding: str
    responsive_instruction: str
    strong_instructional_culture: str
    evidence_of_student_learning: str


def map_daily_content(day: str, content: DailyPlanContent) -> dict[str, str]:
    if day not in WEEKDAYS:
        raise ValueError(f"Unsupported weekday key: {day}")
    return {
        f"clt_{day}": content.clear_learning_target,
        f"rrt_{day}": content.rigorous_relevant_task,
        f"cfu_{day}": content.check_for_understanding,
        f"ri_{day}": content.responsive_instruction,
        f"sic_{day}": content.strong_instructional_culture,
        f"esl_{day}": content.evidence_of_student_learning,
    }


def validate_hqi_payload(payload: dict[str, str]) -> tuple[str, ...]:
    unknown = sorted(set(payload) - set(ALL_HQI_FIELDS))
    return tuple(unknown)
