from datetime import date

import pytest

from app.hqi_composer import WeeklyLessonInput, WeeklyPlanInput, compose_hqi_payload


def base_plan(**overrides: object) -> WeeklyPlanInput:
    values: dict[str, object] = {
        "teacher": "Synthetic Teacher",
        "course": "LET 1",
        "grade": "9-12",
        "week_of": date(2026, 8, 10),
        "unit_topic": "JROTC Foundations",
        "standards": ("Army JROTC competency: leadership foundations",),
        "know": ("Cadet Creed", "program expectations"),
        "understand": ("Cadet responsibility supports team success",),
        "do": ("Demonstrate basic customs and courtesies",),
        "proficiency_scale": (
            "Cadet accurately explains expectations and demonstrates required procedures."
        ),
        "daily_lessons": (
            WeeklyLessonInput(
                day_key="mon",
                learning_target="Explain JROTC expectations and the Cadet Creed.",
                task="Analyze scenarios and connect expectations to cadet responsibilities.",
                check_for_understanding="Retrieval prompt, cold call, and exit ticket.",
                responsive_instruction=(
                    "Reteach vocabulary; extend with peer-led scenario analysis."
                ),
                instructional_culture="Think time, partner talk, and assigned group roles.",
                evidence="Completed scenario response and exit ticket.",
            ),
        ),
    }
    values.update(overrides)
    return WeeklyPlanInput(**values)  # type: ignore[arg-type]


def test_composer_maps_weekly_and_daily_content() -> None:
    payload = compose_hqi_payload(base_plan())

    assert payload["course"] == "LET 1"
    assert payload["week_of"] == "August 10, 2026"
    assert payload["know"] == "Cadet Creed • program expectations"
    assert payload["clt_mon"].startswith("Explain JROTC")
    assert payload["reflect_12"] == ""


def test_composer_rejects_duplicate_weekdays() -> None:
    daily = base_plan().daily_lessons[0]
    with pytest.raises(ValueError, match="Only one daily HQI entry"):
        compose_hqi_payload(base_plan(daily_lessons=(daily, daily)))


def test_composer_requires_all_reflection_slots_without_inventing_content() -> None:
    with pytest.raises(ValueError, match="Exactly 12"):
        compose_hqi_payload(base_plan(reflections=("",) * 11))


def test_composer_rejects_content_that_would_clip_in_pdf() -> None:
    with pytest.raises(ValueError, match="safe layout limits"):
        compose_hqi_payload(base_plan(unit_topic="x" * 91))
