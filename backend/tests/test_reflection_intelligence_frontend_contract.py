from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIENCE = ROOT / "frontend" / "src" / "ReflectionIntelligenceExperience.tsx"
STYLES = ROOT / "frontend" / "src" / "reflection-intelligence.css"
MAIN = ROOT / "frontend" / "src" / "main.tsx"


def test_reflection_intelligence_is_mounted_in_authenticated_app() -> None:
    source = MAIN.read_text(encoding="utf-8")
    assert 'import { ReflectionIntelligenceExperience }' in source
    assert "<ReflectionIntelligenceExperience />" in source


def test_teacher_recap_requires_explicit_boundary_confirmation() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")
    assert "boundaryConfirmed" in source
    assert "Confirm the no-student-data boundary" in source
    assert "class- or group-level observations only" in source
    assert "student names, identifiers" in source
    assert "IEP/504" in source


def test_teacher_reflection_insights_are_scoped_to_friday_step_four() -> None:
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
    assert ".ri-launcher" not in styles
    assert "position: fixed" not in styles.split(".ri-panel", 1)[0]


def test_teacher_reflection_insights_remain_private_and_non_evaluative() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")

    assert "Your private reflection insights" in source
    assert "Instructional insight, not evaluation" in source
    assert "No teacher quality score" in source
    assert "only your submitted teacher-authored professional reflections" in source
    assert 'scope: "private-teacher"' in source
    assert 'evaluation: "none"' in source
    assert "/api/v1/reflection-intelligence/teacher/" in source
    assert "/api/v1/reflection-intelligence/school/" not in source


def test_reflection_intelligence_exposes_no_teacher_comparison_controls() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8").lower()
    forbidden = (
        "teacher score",
        "teacher rating",
        "rank teachers",
        "compare teachers",
        "performance score",
    )
    for phrase in forbidden:
        assert phrase not in source
