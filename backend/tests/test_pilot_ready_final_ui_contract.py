from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"


def test_course_setup_uses_class_selection_language() -> None:
    source = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")

    assert "Select a class to view or edit setup" in source
    assert '"Select class"' in source
    assert '"Selected"' in source
    assert '"Continue setup"' not in source


def test_planning_draft_generation_is_a_primary_action() -> None:
    source = (FRONTEND / "AiPlanningPanel.tsx").read_text(encoding="utf-8")

    assert 'className="primary" onClick={() => void suggest(false)}' in source
    assert 'result ? "Generate a new draft" : "Generate planning draft"' in source
