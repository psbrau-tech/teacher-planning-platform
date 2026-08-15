from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIENCE = ROOT / "frontend" / "src" / "PlcFacilitationArtifactExperience.tsx"
STYLE = ROOT / "frontend" / "src" / "plc-facilitation-artifact.css"
MAIN = ROOT / "frontend" / "src" / "main.tsx"
DECISION = (
    ROOT
    / "docs"
    / "governance"
    / "PLC_FACILITATION_ARTIFACT_DECISION_2026-08-14.md"
)


def test_plc_artifact_uses_governed_school_brief_and_existing_telemetry() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")

    assert "/api/v1/reflection-intelligence/school/" in source
    assert "/handout-viewed" in source
    assert "/api/v1/ai" not in source
    assert "openai" not in source.lower()
    assert 'scope: "school-aggregate"' in source
    assert 'evaluation: "none"' in source


def test_plc_artifact_is_condensed_and_has_fixed_facilitation_protocol() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")

    assert "items.slice(0, 3)" in source
    assert "40-minute PLC protocol" in source
    protocol_steps = (
        "5 min · Orient",
        "10 min · Examine",
        "10 min · Exchange",
        "10 min · Decide",
        "5 min · Commit",
    )
    for minutes in protocol_steps:
        assert minutes in source
    assert "Action we will try:" in source
    assert "Evidence we will bring back:" in source
    assert "Support or resource needed:" in source
    assert "Revisit date:" in source


def test_plc_artifact_preserves_professional_learning_and_data_boundaries() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8").lower()

    assert "anonymous teacher sources" in source
    assert "not teacher-performance measures" in source
    assert "no student data" in source
    assert "no teacher" in source
    assert "ranking" in source
    assert "personnel evaluation" in source
    assert "do not add student-specific information" in source
    assert "tpp does not store these entries" in source
    assert "teacher_name" not in source
    assert "student_name" not in source


def test_print_contract_targets_letter_and_only_the_handout() -> None:
    source = STYLE.read_text(encoding="utf-8").lower()

    assert "@media print" in source
    assert "size: letter portrait" in source
    assert ".plc-facilitation-handout" in source
    assert "visibility: hidden !important" in source
    assert "visibility: visible !important" in source
    assert "break-inside: avoid" in source


def test_plc_artifact_is_mounted_and_governance_defers_retained_action_tracking() -> None:
    main = MAIN.read_text(encoding="utf-8")
    decision = DECISION.read_text(encoding="utf-8").lower()

    assert 'import { PlcFacilitationArtifactExperience }' in main
    assert "<PlcFacilitationArtifactExperience />" in main
    assert "one-to-two-page" in decision
    assert "does not persist" in decision
    assert "persisted plc action tracking" in decision
    assert "separate future governance decisions" in decision
