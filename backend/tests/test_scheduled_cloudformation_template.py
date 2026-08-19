from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "infra" / "scheduled-admin-digest-stack.yml"


def test_scheduled_notification_template_avoids_yaml_aliases() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    # AWS CloudFormation rejects YAML anchors/aliases even though general YAML parsers accept them.
    assert "&ScheduledEnvironment" not in template
    assert "*ScheduledEnvironment" not in template
    assert "&ScheduledSecrets" not in template
    assert "*ScheduledSecrets" not in template
    assert "&ScheduledNetwork" not in template
    assert "*ScheduledNetwork" not in template


def test_scheduled_notification_worker_boundaries_are_explicit_for_both_tasks() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert template.count("- Name: TPP_SUPABASE_SERVICE_ROLE_KEY") == 2
    assert template.count("- Name: TPP_SUPABASE_URL") == 2
    assert template.count("- Name: TPP_SES_FROM_EMAIL") == 2
    assert template.count("- Name: TPP_SES_REGION") == 2
    assert template.count("AssignPublicIp: ENABLED") == 2
