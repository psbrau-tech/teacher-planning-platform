from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "docs"
    / "governance"
    / "REFLECTION_WORKFLOW_PLC_GUIDE_DECISION_2026-08-15.md"
)
HELP = ROOT / "frontend" / "src" / "HelpPage.tsx"


def test_reflection_workflow_decision_locks_optional_friday_step_four() -> None:
    decision = DECISION.read_text(encoding="utf-8").lower()
    help_source = HELP.read_text(encoding="utf-8")

    assert "reflection intelligence is no longer presented as a floating control" in decision
    assert "4. review private reflection insights, if useful" in decision
    assert "5. continue to the following week" in decision
    assert "step 4 is optional" in decision
    assert "must not block step 5" in decision
    assert "4. Review Reflection Insights if useful" in help_source
    assert "5. Continue to the following week" in help_source


def test_plc_meeting_guide_decision_requires_embedded_school_summary() -> None:
    decision = DECISION.read_text(encoding="utf-8").lower()
    help_source = HELP.read_text(encoding="utf-8")

    assert "school reflection summary → plc meeting guide" in decision
    assert "must embed the school reflection summary" in decision
    assert "rather than operating as a generic agenda" in decision
    assert "action workspace remains non-persistent" in decision
    assert "The PLC Meeting Guide follows and carries that School Reflection Summary" in help_source
