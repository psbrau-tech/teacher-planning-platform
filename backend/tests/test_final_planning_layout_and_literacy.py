from pathlib import Path


def test_week_at_a_glance_uses_matrix_layout() -> None:
    source = Path("../frontend/src/PlanningPdfFieldsPanel.tsx").read_text(encoding="utf-8")
    assert '<table className="week-at-glance-matrix">' in source
    assert '<th scope="col">Instructional component</th>' in source
    assert 'COMPONENTS.map(([prefix, label])' in source
    assert 'DAYS.map(([suffix, _dayKey, dayLabel])' in source
    assert 'week-at-glance-day' not in source


def test_governed_literacy_cannot_silently_disappear_from_ai_draft() -> None:
    source = Path("../frontend/src/AiPlanningPanel.tsx").read_text(encoding="utf-8")
    assert 'Required governed literacy recommendation' in source
    assert 'requireGovernedLiteracySuggestion(body.suggestions)' in source
    assert 'requireGovernedLiteracySuggestion(suggestions)' in source
    assert 'Use governed literacy standard' in source
    assert 'will not silently continue with a blank governed literacy field' in source
