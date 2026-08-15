from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIENCE = ROOT / "frontend" / "src" / "PlcFacilitationArtifactExperience.tsx"


def test_optional_assessment_network_failure_cannot_block_reflection_handout() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")

    assert "Promise.allSettled" in source
    assert 'briefResult.status === "rejected"' in source
    assert 'assessmentResult.status === "fulfilled" && assessmentResult.value.ok' in source
    assert "setBrief(await briefResponse.json() as SchoolBrief)" in source
    assert "setAssessmentSnapshot(null)" in source
    assert "optional formative-assessment planning snapshot is unavailable" in source


def test_reflection_brief_remains_required_while_assessment_snapshot_is_optional() -> None:
    source = " ".join(EXPERIENCE.read_text(encoding="utf-8").split())

    assert "if (!briefResponse.ok)" in source
    assert "throw new Error(await readError" in source
    assert "if (assessmentResult.status === \"fulfilled\" && assessmentResult.value.ok)" in source
    assert "The reflection-based handout is ready" in source
