from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIENCE = ROOT / "frontend" / "src" / "ReflectionIntelligenceExperience.tsx"
REFLECTION_ENTRY = ROOT / "frontend" / "src" / "AiReflectionPanel.tsx"
STYLES = ROOT / "frontend" / "src" / "reflection-intelligence.css"
MAIN = ROOT / "frontend" / "src" / "main.tsx"


def test_reflection_intelligence_is_mounted_in_authenticated_app() -> None:
    source = MAIN.read_text(encoding="utf-8")
    assert 'import { ReflectionIntelligenceExperience }' in source
    assert "<ReflectionIntelligenceExperience />" in source


def test_teacher_recap_uses_entry_boundary_without_redundant_step_four_attestation() -> None:
    insight_source = EXPERIENCE.read_text(encoding="utf-8")
    entry_source = REFLECTION_ENTRY.read_text(encoding="utf-8")

    assert "boundaryConfirmed" not in insight_source
    assert 'type="checkbox"' not in insight_source
    assert "governed local data-boundary preflight" in insight_source
    assert "Instructional insight, not evaluation" in insight_source

    assert "Use class- or group-level observations only" in entry_source
    assert "student names, identifiers" in entry_source
    assert "IEP/504" in entry_source
    assert "describe groups or instructional needs rather than individual students" in entry_source


def test_teacher_reflection_insights_are_scoped_inline_to_friday_step_four() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")

    assert "findFridayValidationPanel" in source
    assert '"Friday closeout"' in source
    assert "data-ri-friday-step-host" in source
    assert "data-ri-step-marker-host" in source
    assert "Step 4 · Optional" in source
    assert "Review your reflection insights" in source
    assert "Reflection insights are optional" in source
    assert "Step 5 Continue" in source
    assert "ri-renumbered-continue-marker" in source
    assert "ri-renumbered-continue-card" in source
    assert "ri-inline-body" in source
    assert "Generate my private recap" in source
    assert "ri-results" in source
    assert "<aside" not in source
    assert 'className="ri-panel"' not in source
    assert "setOpen(" not in source
    assert ".ri-panel" not in styles
    assert "position: fixed" not in styles


def test_teacher_reflection_insights_remain_private_and_non_evaluative() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")

    assert "Review your reflection insights" in source
    assert "Instructional insight, not evaluation" in source
    assert "No teacher quality score" in source
    assert "only your submitted teacher-authored professional reflections" in source
    assert 'scope: "private-teacher"' in source
    assert 'evaluation: "none"' in source
    assert "/api/v1/reflection-intelligence/teacher/" in source
    assert "/api/v1/reflection-intelligence/school/" not in source


def test_reflection_intelligence_exposes_no_teacher_comparison_controls() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8").lower()
    forbidden_controls = (
        "teacher score:",
        "teacher rating:",
        "rank teachers",
        "compare teachers",
        "performance score:",
    )
    for phrase in forbidden_controls:
        assert phrase not in source

    # Negative boundary language is expected and must remain visible.
    assert "not a teacher-performance score" in source
    assert "no teacher quality score" in source
