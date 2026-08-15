from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELP = ROOT / "frontend" / "src" / "HelpPage.tsx"
DEPLOY = ROOT / ".github" / "workflows" / "deploy-pilot.yml"


def test_help_covers_current_teacher_workflow_and_curriculum_lifecycle() -> None:
    source = HELP.read_text(encoding="utf-8")
    required = (
        "Step 1 — Class & Schedule",
        "Step 2 — Curriculum & Pacing",
        "Save Curriculum & Pacing & Continue",
        "Add another class",
        "Each class has independent progress",
        "Edit current curriculum",
        "Update shared future pacing",
        "Create a separate copy for this class",
        "Download Excel",
        "Create new version / copy",
        "Monday through Friday",
        "Reflection / PLC Discussion prompts",
        "Completed Weekly Packet",
        "Do not enter student names",
    )
    for phrase in required:
        assert phrase in source, f"Help is missing current workflow guidance: {phrase}"


def test_pilot_deployment_requires_exact_candidate_help_review_acknowledgement() -> None:
    workflow = DEPLOY.read_text(encoding="utf-8")
    assert "help_review_confirmed:" in workflow
    assert "I reviewed Help against this exact release candidate and it is current" in workflow
    assert "Enforce release confirmations" in workflow
    assert "inputs.help_review_confirmed" in workflow
    assert (
        "Pilot deployment is blocked until Help is reviewed against this exact release candidate"
        in workflow
    )
