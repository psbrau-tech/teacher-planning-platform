"""Deterministic composition of structured weekly plans into the Anniston HQI form."""

from dataclasses import dataclass, field
from datetime import date

from .pdf_fields import DailyPlanContent, map_daily_content, validate_field_lengths

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri")


@dataclass(frozen=True, slots=True)
class WeeklyLessonInput:
    day_key: str
    learning_target: str
    task: str
    check_for_understanding: str
    responsive_instruction: str
    instructional_culture: str
    evidence: str


@dataclass(frozen=True, slots=True)
class WeeklyPlanInput:
    teacher: str
    course: str
    grade: str
    week_of: date
    unit_topic: str
    standards: tuple[str, ...]
    know: tuple[str, ...]
    understand: tuple[str, ...]
    do: tuple[str, ...]
    proficiency_scale: str
    literacy_standards: tuple[str, ...] = ()
    act_preparation: str = ""
    misconceptions: tuple[str, ...] = ()
    formative_assessments: tuple[str, ...] = ()
    summative_assessments: tuple[str, ...] = ()
    performance_task: str = ""
    resources: tuple[str, ...] = ()
    daily_lessons: tuple[WeeklyLessonInput, ...] = ()
    reflections: tuple[str, ...] = field(default_factory=lambda: ("",) * 12)


def _join(items: tuple[str, ...]) -> str:
    return " • ".join(item.strip() for item in items if item.strip())


def compose_hqi_payload(plan: WeeklyPlanInput) -> dict[str, str]:
    if len(plan.reflections) != 12:
        raise ValueError("Exactly 12 reflection responses are required")

    daily_keys = [lesson.day_key for lesson in plan.daily_lessons]
    invalid_days = sorted(set(daily_keys) - set(DAY_KEYS))
    if invalid_days:
        raise ValueError(f"Unsupported daily lesson keys: {', '.join(invalid_days)}")
    if len(daily_keys) != len(set(daily_keys)):
        raise ValueError("Only one daily HQI entry may be supplied per weekday")

    payload: dict[str, str] = {
        "teacher": plan.teacher,
        "course": plan.course,
        "grade": plan.grade,
        "week_of": plan.week_of.strftime("%B %-d, %Y"),
        "unit_topic": plan.unit_topic,
        "standards": _join(plan.standards),
        "literacy_standards": _join(plan.literacy_standards),
        "act_preparation": plan.act_preparation,
        "know": _join(plan.know),
        "understand": _join(plan.understand),
        "do": _join(plan.do),
        "plds": plan.proficiency_scale,
        "misconceptions": _join(plan.misconceptions),
        "formative": _join(plan.formative_assessments),
        "summative": _join(plan.summative_assessments),
        "performance_task": plan.performance_task,
        "resources": _join(plan.resources),
    }

    for lesson in plan.daily_lessons:
        payload.update(
            map_daily_content(
                lesson.day_key,
                DailyPlanContent(
                    clear_learning_target=lesson.learning_target,
                    rigorous_relevant_task=lesson.task,
                    check_for_understanding=lesson.check_for_understanding,
                    responsive_instruction=lesson.responsive_instruction,
                    strong_instructional_culture=lesson.instructional_culture,
                    evidence_of_student_learning=lesson.evidence,
                ),
            )
        )

    for index, response in enumerate(plan.reflections, start=1):
        payload[f"reflect_{index}"] = response

    length_errors = validate_field_lengths(payload)
    if length_errors:
        detail = ", ".join(
            f"{error.field}={error.character_count}/{error.character_limit}"
            for error in length_errors
        )
        raise ValueError(f"HQI content exceeds application limits: {detail}")

    return payload
