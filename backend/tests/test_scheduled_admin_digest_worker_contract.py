from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app import scheduled_digest_worker as worker
from app.settings import APPROVED_SES_FROM_EMAIL, Settings

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815011000_scheduled_admin_digest_worker.sql"
)
SCHEDULED_STACK = ROOT / "infra" / "scheduled-admin-digest-stack.yml"
MAIN_STACK = ROOT / "infra" / "pilot-stack.yml"
ACTIVATION_WORKFLOW = ROOT / ".github" / "workflows" / "enable-scheduled-admin-digest.yml"
CFN_POLICY = ROOT / "infra" / "iam" / "tpp-cloudformation-execution-policy.json"
OIDC_POLICY = ROOT / "infra" / "iam" / "tpp-github-oidc-deployment-policy.json"
OWNER_ANALYTICS = ROOT / "frontend" / "src" / "OwnerReflectionIntelligenceAnalytics.tsx"
NOTIFICATION_API = ROOT / "backend" / "app" / "notifications_api.py"


def test_worker_uses_school_local_monday() -> None:
    sunday_utc = datetime(2026, 8, 17, 2, 30, tzinfo=timezone.utc)
    assert worker.week_start_for_timezone("America/Chicago", sunday_utc).isoformat() == (
        "2026-08-10"
    )


def test_worker_rejects_any_sender_other_than_locked_tpp_address() -> None:
    settings = Settings(ses_from_email="other@planner.guidedscholar.ai")
    with pytest.raises(worker.ScheduledDigestWorkerError, match="approved TPP address"):
        worker.run_scheduled_admin_digest(settings)


def test_worker_sends_only_claimed_governed_recipient_and_records_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        ses_from_email=APPROVED_SES_FROM_EMAIL,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-placeholder",
        allowed_email_domains="anniston.k12.al.us",
        scheduled_digest_timezone="America/Chicago",
    )
    candidate: dict[str, Any] = {
        "delivery_id": "claim-1",
        "school_id": "school-1",
        "recipient_profile_id": "admin-1",
        "recipient_email": "principal@anniston.k12.al.us",
        "configured_assignments": 20,
        "lesson_plans_submitted": 18,
        "lesson_plans_missing": 2,
        "completed_packets_submitted": 16,
        "completed_packets_missing": 4,
        "teachers_with_completed_packets": 8,
    }
    sent: list[tuple[str, int]] = []
    completions: list[tuple[str, bool]] = []
    fake_client = object()

    monkeypatch.setattr(worker, "_service_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        worker,
        "week_start_for_timezone",
        lambda _timezone: datetime(2026, 8, 10).date(),
    )
    monkeypatch.setattr(
        worker,
        "_claim_candidates",
        lambda _client, *, week_start: [candidate],
    )
    monkeypatch.setattr(
        worker,
        "send_weekly_admin_digest",
        lambda _settings, *, recipient_email, metrics: sent.append(
            (recipient_email, metrics.configured_assignments)
        )
        or "message-id-not-retained",
    )
    monkeypatch.setattr(
        worker,
        "_complete_delivery",
        lambda _client, *, delivery_id, success: completions.append(
            (delivery_id, success)
        ),
    )

    result = worker.run_scheduled_admin_digest(settings)

    assert sent == [("principal@anniston.k12.al.us", 20)]
    assert completions == [("claim-1", True)]
    assert result == {
        "week_start": "2026-08-10",
        "claimed": 1,
        "sent": 1,
        "failed": 0,
    }


def test_worker_rejects_claimed_recipient_outside_governed_email_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        ses_from_email=APPROVED_SES_FROM_EMAIL,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-placeholder",
        allowed_email_domains="anniston.k12.al.us",
    )
    candidate: dict[str, Any] = {
        "delivery_id": "claim-2",
        "recipient_email": "outside@example.org",
        "configured_assignments": 1,
        "lesson_plans_submitted": 1,
        "lesson_plans_missing": 0,
        "completed_packets_submitted": 0,
        "completed_packets_missing": 1,
        "teachers_with_completed_packets": 0,
    }
    completions: list[tuple[str, bool]] = []
    fake_client = object()

    monkeypatch.setattr(worker, "_service_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        worker,
        "week_start_for_timezone",
        lambda _timezone: datetime(2026, 8, 10).date(),
    )
    monkeypatch.setattr(
        worker,
        "_claim_candidates",
        lambda _client, *, week_start: [candidate],
    )
    monkeypatch.setattr(
        worker,
        "send_weekly_admin_digest",
        lambda *_args, **_kwargs: pytest.fail("outside-domain email must not be sent"),
    )
    monkeypatch.setattr(
        worker,
        "_complete_delivery",
        lambda _client, *, delivery_id, success: completions.append(
            (delivery_id, success)
        ),
    )

    result = worker.run_scheduled_admin_digest(settings)

    assert completions == [("claim-2", False)]
    assert result["sent"] == 0
    assert result["failed"] == 1


def test_service_role_database_boundary_is_rpc_only_and_at_most_once() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    table_definition = source.split(
        "create table public.scheduled_notification_deliveries",
        maxsplit=1,
    )[1].split("create index", maxsplit=1)[0]

    assert "recipient_profile_id uuid" in table_definition
    assert "recipient_email" not in table_definition
    assert "email body" not in table_definition.lower()
    assert "unique (notification_key, recipient_profile_id, week_start)" in source
    assert "on conflict (notification_key, recipient_profile_id, week_start) do nothing" in source
    assert "claim_scheduled_admin_weekly_digest_candidates" in source
    assert "complete_scheduled_admin_weekly_digest_delivery" in source
    assert "auth.role()" in source
    assert "<> 'service_role'" in source
    assert "to service_role" in source
    assert "pr.role = 'school_admin'::public.app_role" in source
    assert "teacher_name" not in source
    assert "course_name" not in source
    assert "source_data" not in source


def test_scheduled_task_is_isolated_from_interactive_web_credentials() -> None:
    scheduled = SCHEDULED_STACK.read_text(encoding="utf-8")
    main = MAIN_STACK.read_text(encoding="utf-8")

    assert "TPP_SUPABASE_SERVICE_ROLE_KEY" in scheduled
    assert "TPP_SUPABASE_URL" in scheduled
    assert "TPP_SUPABASE_ANON_KEY" not in scheduled
    assert "TPP_OPENAI_API_KEY" not in scheduled
    assert "TPP_SUPABASE_SERVICE_ROLE_KEY" not in main
    assert "app.scheduled_digest_worker" in scheduled
    assert "ReadonlyRootFilesystem: true" in scheduled
    assert "Action: ses:SendEmail" in scheduled
    assert "Resource: !Ref SesIdentityArn" in scheduled


def test_schedule_is_staged_disabled_and_requires_immutable_image() -> None:
    source = SCHEDULED_STACK.read_text(encoding="utf-8")

    assert "AllowedPattern: '^.+@sha256:[0-9a-f]{64}$'" in source
    assert "Type: AWS::Scheduler::Schedule" in source
    assert "ScheduleExpressionTimezone: !Ref ScheduleTimezone" in source
    assert "ScheduleState:" in source
    assert "Default: DISABLED" in source
    assert "State: !Ref ScheduleState" in source
    assert "LaunchType: FARGATE" in source
    assert "MaximumRetryAttempts: 1" in source


def test_activation_workflow_requires_exact_schedule_and_never_runs_task_immediately() -> None:
    source = ACTIVATION_WORKFLOW.read_text(encoding="utf-8")

    assert "schedule_expression:" in source
    assert "schedule_time_approved:" in source
    assert "database_migration_applied_confirmed:" in source
    assert "ses_notifications_active_confirmed:" in source
    assert "deployment_role_policies_updated_confirmed:" in source
    assert "ScheduleState=DISABLED" in source
    assert "ScheduleState=ENABLED" in source
    assert "notifications@planner.guidedscholar.ai" in source
    assert "supabase-service-role-key-" in source
    assert "aws ecs run-task" not in source.lower()
    assert "send-email" not in source.lower()
    assert "immediate/test email sent by this workflow" in source.lower()


def test_deployment_policies_are_limited_to_exact_scheduled_resources() -> None:
    cfn = CFN_POLICY.read_text(encoding="utf-8")
    oidc = OIDC_POLICY.read_text(encoding="utf-8")

    assert "tpp-pilot-scheduled-digest-task" in cfn
    assert "tpp-pilot-scheduled-digest-task-execution" in cfn
    assert "tpp-pilot-scheduled-digest-scheduler" in cfn
    assert "schedule/default/tpp-pilot-admin-weekly-digest" in cfn
    assert "supabase-service-role-key-*" in cfn
    assert "TeacherPlanningPlatformPilotScheduledDigest/*" in oidc
    assert "schedule/default/tpp-pilot-admin-weekly-digest" in oidc


def test_owner_reporting_distinguishes_scheduled_from_manual_delivery() -> None:
    api = NOTIFICATION_API.read_text(encoding="utf-8")
    ui = OWNER_ANALYTICS.read_text(encoding="utf-8")

    for field in (
        "scheduled_admin_weekly_digests_sent",
        "scheduled_digest_recipient_admins",
        "scheduled_digest_schools",
    ):
        assert field in api
        assert field in ui
    assert "manually triggered" in ui
    assert "scheduled admin digests" in ui
    assert "teacher performance" in ui.lower()
