import pytest

from app.pdf_fields import (
    ALL_HQI_FIELDS,
    DAILY_FIELDS,
    DailyPlanContent,
    map_daily_content,
    validate_hqi_payload,
)


def test_hqi_contract_contains_57_fields() -> None:
    assert len(ALL_HQI_FIELDS) == 57
    assert len(DAILY_FIELDS) == 30


def test_daily_mapping_uses_anniston_field_prefixes() -> None:
    mapped = map_daily_content(
        "mon",
        DailyPlanContent(
            clear_learning_target="Target",
            rigorous_relevant_task="Task",
            check_for_understanding="Check",
            responsive_instruction="Response",
            strong_instructional_culture="Culture",
            evidence_of_student_learning="Evidence",
        ),
    )

    assert mapped == {
        "clt_mon": "Target",
        "rrt_mon": "Task",
        "cfu_mon": "Check",
        "ri_mon": "Response",
        "sic_mon": "Culture",
        "esl_mon": "Evidence",
    }


def test_payload_validation_rejects_unknown_fields() -> None:
    assert validate_hqi_payload({"teacher": "Peter", "unknown": "value"}) == ("unknown",)


def test_daily_mapping_rejects_weekend_key() -> None:
    with pytest.raises(ValueError, match="Unsupported weekday"):
        map_daily_content(
            "sat",
            DailyPlanContent("", "", "", "", "", ""),
        )
