from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-pilot.yml"
EXPECTED_ROLE = (
    "arn:aws:iam::697091778129:role/"
    "TeacherPlanningPlatformPilotCloudFormationExecution"
)


def test_pilot_deploy_uses_dedicated_cloudformation_execution_role() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "CLOUDFORMATION_ROLE_ARN: ${{ vars.TPP_CLOUDFORMATION_ROLE_ARN }}" in workflow
    assert "CLOUDFORMATION_ROLE_ARN" in workflow.split("required=(", 1)[1].split(")", 1)[0]
    assert EXPECTED_ROLE in workflow
    assert '--role-arn "$CLOUDFORMATION_ROLE_ARN"' in workflow
