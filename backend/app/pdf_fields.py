"""Anniston HQI form-field contract and content-size validation."""

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

# These limits protect the application and generated document from accidental
# unbounded input. They are intentionally much larger than the original PDF
# widget limits. The generator removes PDF MaxLen restrictions, enables
# multiline entry, and uses automatic font sizing for narrative fields.
FIELD_CHARACTER_LIMITS: dict[str, int] = {
    "teacher": 120,
    "course": 160,
    "grade": 60,
    "week_of": 60,
    "unit_topic": 500,
    "standards": 2_000,
    "know": 2_000,
    "understand": 2_000,
    "do": 2_000,
    "plds": 2_000,
    "misconceptions": 2_000,
    "formative": 1_500,
    "summative": 1_500,
    "performance_task": 1_500,
    "resources": 1_500,
    **{field: 1_200 for field in DAILY_FIELDS},
    **{field: 2_000 for field in REFLECTION_FIELDS},
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
