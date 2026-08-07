from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_tls_workflow_uses_dedicated_cloudformation_execution_role() -> None:
    workflow = (WORKFLOWS / "enable-pilot-tls.yml").read_text(encoding="utf-8")
    assert "CLOUDFORMATION_ROLE_ARN: ${{ vars.TPP_CLOUDFORMATION_ROLE_ARN }}" in workflow
    assert '--role-arn "$CLOUDFORMATION_ROLE_ARN"' in workflow
    assert "TeacherPlanningPlatformPilotCloudFormationExecution" in workflow
