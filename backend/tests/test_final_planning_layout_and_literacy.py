from pathlib import Path

import pytest
from fastapi import HTTPException

from app.ai_planning_resilient_api import _resolve_valid_literacy


def test_week_at_a_glance_uses_matrix_layout() -> None:
    source = Path("../frontend/src/PlanningPdfFieldsPanel.tsx").read_text(encoding="utf-8")
    assert '<table className="week-at-glance-matrix">' in source
    assert '<th scope="col">Instructional component</th>' in source
    assert 'COMPONENTS.map(([prefix, label])' in source
    assert 'DAYS.map(([suffix, dayLabel])' in source
    assert 'week-at-glance-day' not in source


def test_framework_is_one_continuous_section_before_week_at_a_glance() -> None:
    source = Path("../frontend/src/PlanningPdfFieldsPanel.tsx").read_text(encoding="utf-8")
    framework_summary = '<summary>Instructional Planning Framework</summary>'
    week_summary = '<summary>Week at a Glance</summary>'
    assert framework_summary in source
    assert 'Instructional Planning Framework — remaining fields' not in source
    assert source.index(framework_summary) < source.index(week_summary)
    for label in (
        "Unit / topic",
        "Selected authoritative standards",
        "Know",
        "Understand",
        "Do",
        "Performance-Level Descriptors / Proficiency Scale",
        "Likely Misconceptions",
        "Formative Assessments",
        "Summative Assessments",
        "Performance Task / Authentic Application",
        "Resources",
        "Literacy Standards",
        "ACT Preparation",
    ):
        assert label in source
    assert '>Monday<textarea' not in source
    assert '>Tuesday<textarea' not in source
    assert '>Wednesday<textarea' not in source
    assert '>Thursday<textarea' not in source
    assert '>Friday<textarea' not in source


def test_governed_literacy_cannot_silently_disappear_from_ai_draft() -> None:
    source = Path("../frontend/src/AiPlanningPanel.tsx").read_text(encoding="utf-8")
    assert 'Required governed literacy recommendation' in source
    assert 'requireGovernedLiteracySuggestion(body.suggestions)' in source
    assert 'requireGovernedLiteracySuggestion(suggestions)' in source
    assert 'Use governed literacy standard' in source
    assert 'will not silently continue with a blank governed literacy field' in source


def test_resilient_literacy_resolution_accepts_approved_id_or_unique_code() -> None:
    candidates = [
        {
            "standard_entry_id": "11111111-1111-1111-1111-111111111111",
            "grade_band": "Grade 9",
            "code": "ELA9.R1",
            "authoritative_text": "Read and comprehend complex informational text.",
        }
    ]
    by_id = _resolve_valid_literacy(candidates, ["11111111-1111-1111-1111-111111111111"])
    by_code = _resolve_valid_literacy(candidates, ["ELA9.R1"])
    assert "ELA9.R1" in by_id
    assert by_code == by_id


def test_resilient_literacy_resolution_rejects_unknown_reference_instead_of_blank() -> None:
    candidates = [
        {
            "standard_entry_id": "11111111-1111-1111-1111-111111111111",
            "grade_band": "Grade 9",
            "code": "ELA9.R1",
            "authoritative_text": "Read and comprehend complex informational text.",
        }
    ]
    with pytest.raises(HTTPException) as caught:
        _resolve_valid_literacy(candidates, ["not-an-approved-reference"])
    assert caught.value.status_code == 503
    assert "approved Alabama Literacy Standard" in str(caught.value.detail)
