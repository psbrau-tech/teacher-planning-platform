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
    "plds",
    "misconceptions",
    "formative",
    "summative",
    "performance_task",
    "resources",
)

DAILY_FIELDS = tuple(f"{group}_{day}" for day in WEEKDAYS for group in DAILY_GROUPS)
ALL_HQI_FIELDS = PAGE_ONE_FIELDS + DAILY_FIELDS + REFLECTION_FIELDS

FIELD_CHARACTER_LIMITS: dict[str, int] = {
    "teacher": 45,
    "course": 55,
    "grade": 20,
    "week_of": 30,
    "unit_topic": 90,
    "standards": 220,
    "know": 260,
    "understand": 260,
    "do": 260,
    "plds": 260,
    "misconceptions": 260,
    "formative": 180,
    "summative": 180,
    "performance_task": 180,
    "resources": 180,
    **{field: 145 for field in DAILY_FIELDS},
    **{field: 220 for field in REFLECTION_FIELDS},
}


@dataclass(frozen=True, slots=True)
class DailyPlanContent:
    clear_learning_target: str
    rigorous_relevant_task: str
    check_for_understanding: str
    responsive_instruction: str
    strong_instructional_culture: str
    evidence_of_student_learning: str


@dataclass(frozen=True, slots=True)
class FieldLengthError:
    field: str
    character_count: int
    character_limit: int


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


def validate_field_lengths(payload: dict[str, str]) -> tuple[FieldLengthError, ...]:
    errors = [
        FieldLengthError(
            field=field,
            character_count=len(value),
            character_limit=FIELD_CHARACTER_LIMITS[field],
        )
        for field, value in payload.items()
        if field in FIELD_CHARACTER_LIMITS and len(value) > FIELD_CHARACTER_LIMITS[field]
    ]
    return tuple(sorted(errors, key=lambda item: item.field))
