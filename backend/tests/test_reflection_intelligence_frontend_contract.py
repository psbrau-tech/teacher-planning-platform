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


def test_school_plc_brief_remains_aggregate_and_non_evaluative() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")
    assert "Instructional insight, not evaluation" in source
    assert "No teacher quality score" in source
    assert "anonymous teacher source references" in source
    assert "at least two distinct teachers" in source
    assert "Supported by {item.source_refs.length} anonymous teacher sources" in source


def test_plc_handout_is_transient_print_markup() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")
    assert "reflection-intelligence-handout" in source
    assert "Print PLC handout" in source
    assert "window.print()" in source
    assert "@media print" in styles
    assert "visibility: hidden" in styles
    assert "AI-synthesized from teacher-authored submitted reflections" in source


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
