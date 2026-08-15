from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "infra" / "pilot-stack.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "enable-ses-notifications.yml"
SETTINGS = ROOT / "backend" / "app" / "settings.py"
DECISION = (
    ROOT
    / "docs"
    / "governance"
    / "SES_NOTIFICATION_INFRASTRUCTURE_DECISION_2026-08-14.md"
)

APPROVED_SENDER = "notifications@planner.guidedscholar.ai"


def test_cloudformation_keeps_ses_fail_closed_until_both_values_are_supplied() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "SesFromEmail:" in source
    assert "SesIdentityArn:" in source
    assert source.count("Default: ''") >= 5
    assert "UseSesNotifications: !And" in source
    assert "!Ref SesFromEmail" in source
    assert "!Ref SesIdentityArn" in source
    assert "Condition: UseSesNotifications" in source


def test_task_role_ses_permission_is_single_action_and_identity_scoped() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")
    policy = source.split("SesSendPolicy:", maxsplit=1)[1].split(
        "TaskDefinition:", maxsplit=1
    )[0]

    assert "Type: AWS::IAM::Policy" in policy
    assert "Action: ses:SendEmail" in policy
    assert "Resource: !Ref SesIdentityArn" in policy
    assert "ses:SendRawEmail" not in policy
    assert "Resource: '*'" not in policy
    assert "access-key" not in source.lower()


def test_task_definition_receives_sender_and_region_without_new_secrets() -> None:
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "Name: TPP_SES_FROM_EMAIL" in source
    assert "Value: !Ref SesFromEmail" in source
    assert "Name: TPP_SES_REGION" in source
    assert "Value: !Ref AWS::Region" in source
    assert "Name: TPP_AWS_ACCESS_KEY_ID" not in source
    assert "Name: TPP_AWS_SECRET_ACCESS_KEY" not in source


def test_activation_workflow_locks_identity_and_manual_release_gates() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert f"SES_FROM_EMAIL: {APPROVED_SENDER}" in source
    assert "sender_identity_verified" in source
    assert "production_access_confirmed" in source
    assert "privacy_help_review_confirmed" in source
    assert "identity/notifications@planner.guidedscholar.ai" in source
    assert "identity/planner.guidedscholar.ai" in source
    assert 'SesFromEmail="$SES_FROM_EMAIL"' in source
    assert 'SesIdentityArn="$SES_IDENTITY_ARN"' in source
    assert "Email sent by this workflow: \\`false\\`" in source
    assert "send-email" not in source.lower()
    assert "sesv2 send" not in source.lower()


def test_activation_preserves_exact_image_and_existing_runtime_secret_set() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "@sha256:[0-9a-f]{64}" in source
    expected_secret_set = (
        "TPP_OPENAI_API_KEY\\nTPP_SUPABASE_ANON_KEY\\nTPP_SUPABASE_URL"
    )
    assert expected_secret_set in source
    assert 'image" != "${{ steps.baseline.outputs.image }}"' in source
    assert "SES activation changed the accepted application image" in source


def test_application_default_and_governance_keep_delivery_disabled_before_activation() -> None:
    settings = SETTINGS.read_text(encoding="utf-8")
    decision = DECISION.read_text(encoding="utf-8").lower()

    assert 'ses_from_email: str = ""' in settings
    assert APPROVED_SENDER in decision
    assert "ses delivery remains disabled by default" in decision
    assert "does not send a test email" in decision
    assert "student pii" in decision
    assert "no ses activation" in decision
