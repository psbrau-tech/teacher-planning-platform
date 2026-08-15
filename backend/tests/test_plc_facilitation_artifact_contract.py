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
    assert "OpenAI(" not in source
    assert "new OpenAI" not in source
    assert 'scope: "school-aggregate"' in source
    assert 'evaluation: "none"' in source


def test_plc_artifact_adds_only_governed_aggregate_assessment_snapshot() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")

    assert "/api/v1/assessment-analytics/school?" in source
    assert 'source_scope: "immutable-submitted-lesson-plans"' in source
    assert 'classification_method: "deterministic-keyword-v1"' in source
    assert 'interpretation: "planned-formative-assessment-signals-only"' in source
    assert "Exit tickets / slips" not in source
    assert 'key === "exit_ticket"' in source
    assert ".slice(0, 3)" in source
    assert "no assessment text sent to AI" in source
    assert "daily_assessment_data" not in source
    assert "teacher_name" not in source
    assert "course_name" not in source
    assert "student_name" not in source


def test_assessment_snapshot_is_optional_and_does_not_block_reflection_handout() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")

    assert "if (assessmentResponse.ok)" in source
    assert "setAssessmentSnapshot(null)" in source
    assert "optional formative-assessment planning snapshot is unavailable" in source
    assert "setBrief(await briefResponse.json() as SchoolBrief)" in source


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
    assert "planned assessment signals only" in source
    assert "student results" in source
    assert "teacher effectiveness" in source
    assert "ranking" in source
    assert "personnel evaluation" in source
    assert "do not add student-specific information" in source
    assert "tpp does not store these entries" in source
    assert "teacher_name" not in source
    assert "student_name" not in source


def test_print_contract_targets_letter_and_keeps_snapshot_compact() -> None:
    source = STYLE.read_text(encoding="utf-8").lower()

    assert "@media print" in source
    assert "size: letter portrait" in source
    assert ".plc-facilitation-handout" in source
    assert "visibility: hidden !important" in source
    assert "visibility: visible !important" in source
    assert ".plc-assessment-snapshot" in source
    assert "break-inside: avoid" in source


def test_plc_artifact_governance_defers_retained_action_and_combined_profile_tracking() -> None:
    main = MAIN.read_text(encoding="utf-8")
    decision = DECISION.read_text(encoding="utf-8").lower()

    assert 'import { PlcFacilitationArtifactExperience }' in main
    assert "<PlcFacilitationArtifactExperience />" in main
    assert "one-to-two-page" in decision
    assert "aggregate formative-assessment planning snapshot" in decision
    assert "must not send lesson-plan text to openai" in decision
    assert "does not persist" in decision
    assert "persisted plc action tracking" in decision
    assert "combined-profile telemetry" in decision
    assert "separate future governance decisions" in decision
