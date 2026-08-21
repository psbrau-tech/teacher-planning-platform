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
    assert 'className="week-at-glance-component-row"' in source
    assert 'onPointerDown={beginRowResize}' in source
    assert 'setRowHeight(Math.max(MIN_MATRIX_ROW_HEIGHT' in source
    assert 'week-at-glance-day' not in source
    assert "Prefill matching fields" not in source


def test_framework_is_one_continuous_section_in_canonical_pdf_order() -> None:
    source = Path("../frontend/src/PlanningPdfFieldsPanel.tsx").read_text(encoding="utf-8")
    framework_summary = '<summary>Instructional Planning Framework</summary>'
    week_summary = '<summary>Week at a Glance</summary>'
    assert framework_summary in source
    assert 'Instructional Planning Framework — remaining fields' not in source
    assert 'Supporting planning notes' not in source
    assert source.index(framework_summary) < source.index(week_summary)
    labels = (
        "Unit / topic",
        "Selected authoritative standards",
        "Literacy Standards",
        "ACT Preparation",
        "Know",
        "Understand",
        "Do",
        "Performance-Level Descriptors / Proficiency Scale",
        "Likely Misconceptions",
        "Formative Assessments",
        "Summative Assessments",
        "Performance Task / Authentic Application",
        "Resources",
    )
    positions = [source.index(label, source.index(framework_summary)) for label in labels]
    assert positions == sorted(positions)
    assert '>Monday<textarea' not in source
    assert '>Tuesday<textarea' not in source
    assert '>Wednesday<textarea' not in source
    assert '>Thursday<textarea' not in source
    assert '>Friday<textarea' not in source


def test_ai_review_follows_pdf_order_without_non_pdf_sections() -> None:
    source = Path("../frontend/src/AiPlanningPanel.tsx").read_text(encoding="utf-8")
    framework_group = (
        '{ label: "Instructional Planning Framework", fields: '
        '["unit_topic", "literacy_standards", "act_preparation", "know", "understand", '
        '"do_statement", "plds", "misconceptions", "formative", "summative", '
        '"performance_task", "resources"] }'
    )
    assert framework_group in source
    assert 'label: "Supporting instructional design"' not in source
    assert 'label: "Daily planning notes"' not in source
    assert source.index(framework_group) < source.index(
        'label: "Week at a Glance — Clear learning target & success criteria"'
    )


def test_governed_literacy_cannot_silently_disappear_from_ai_draft() -> None:
    source = Path("../frontend/src/AiPlanningPanel.tsx").read_text(encoding="utf-8")
    assert '"literacy_standards"' in source
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
