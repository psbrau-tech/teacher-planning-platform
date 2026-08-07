from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
IAM_DIR = ROOT / "infra" / "iam"


def _load(name: str) -> dict[str, Any]:
    with (IAM_DIR / name).open(encoding="utf-8") as policy_file:
        value = json.load(policy_file)
    assert value["Version"] == "2012-10-17"
    assert isinstance(value["Statement"], list)
    return value


def _statements_by_sid(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {statement["Sid"]: statement for statement in policy["Statement"] if "Sid" in statement}


def test_cloudformation_execution_trust_is_service_only() -> None:
    policy = _load("tpp-cloudformation-execution-trust.json")
    assert policy["Statement"] == [
        {
            "Effect": "Allow",
            "Principal": {"Service": "cloudformation.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ]


def test_github_role_can_pass_only_the_exact_cloudformation_role() -> None:
    policy = _load("tpp-github-oidc-deployment-policy.json")
    statements = _statements_by_sid(policy)
    pass_role = statements["PassExactCloudFormationExecutionRole"]
    assert pass_role["Action"] == "iam:PassRole"
    assert pass_role["Resource"] == (
        "arn:aws:iam::697091778129:role/"
        "TeacherPlanningPlatformPilotCloudFormationExecution"
    )
    assert pass_role["Condition"] == {
        "StringEquals": {"iam:PassedToService": "cloudformation.amazonaws.com"}
    }


def test_github_stack_access_is_limited_to_the_named_pilot_stack() -> None:
    policy = _load("tpp-github-oidc-deployment-policy.json")
    statements = _statements_by_sid(policy)
    stack_access = statements["ManageNamedPilotStack"]
    assert (
        "arn:aws:cloudformation:us-east-2:697091778129:"
        "stack/TeacherPlanningPlatformPilot/*"
    ) in stack_access["Resource"]
    assert stack_access["Condition"]["StringEqualsIfExists"]["cloudformation:RoleArn"] == (
        "arn:aws:iam::697091778129:role/"
        "TeacherPlanningPlatformPilotCloudFormationExecution"
    )


def test_execution_role_can_manage_only_the_two_pilot_task_roles() -> None:
    policy = _load("tpp-cloudformation-execution-policy.json")
    statements = _statements_by_sid(policy)
    role_management = statements["ManageExactPilotTaskRoles"]
    assert set(role_management["Resource"]) == {
        "arn:aws:iam::697091778129:role/tpp-pilot-task",
        "arn:aws:iam::697091778129:role/tpp-pilot-task-execution",
    }
