from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app import scheduled_digest_worker as worker
from app.notification_email import (
    FridayAdminDigestMetrics,
    FridayTeacherReminderItem,
    friday_admin_digest_text,
    teacher_friday_reminder_text,
)
from app.settings import APPROVED_SES_FROM_EMAIL, Settings

ROOT = Path(__file__).resolve().parents[2]
STATUS_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815011000_friday_submission_status.sql"
)
DELIVERY_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815013000_scheduled_friday_notifications.sql"
)
MULTI_SCHOOL_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815215500_multi_school_notification_controls.sql"
)
WINDOW_HARDENING_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815220500_harden_school_local_notification_windows.sql"
)
CLAIM_CONFLICT_REPAIR_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260821201500_fix_scheduled_notification_claim_conflicts.sql"
)
SCHEDULED_STACK = ROOT / "infra" / "scheduled-admin-digest-stack.yml"
MAIN_STACK = ROOT / "infra" / "pilot-stack.yml"
ACTIVATION_WORKFLOW = (
    ROOT / ".github" / "workflows" / "enable-scheduled-admin-digest.yml"
)
CFN_POLICY = ROOT / "infra" / "iam" / "tpp-cloudformation-execution-policy.json"
OIDC_POLICY = ROOT / "infra" / "iam" / "tpp-github-oidc-deployment-policy.json"
MAIN_FRONTEND = ROOT / "frontend" / "src" / "main.tsx"

SCHOOL_ID = "11111111-1111-4111-8111-111111111111"


def test_worker_uses_school_local_monday() -> None:
    sunday_utc = datetime(2026, 8, 17, 2, 30, tzinfo=UTC)
    assert (
        worker.week_start_for_timezone("America/Chicago", sunday_utc).isoformat()
        == "2026-08-10"
    )


def test_dispatch_window_is_explicitly_school_scoped_and_timezone_checked() -> None:
    class FakeClient:
        def request(
            self,
            method: str,
            path: str,
            *,
            payload: dict[str, str],
        ) -> object:
            assert method == "POST"
            assert path == "rpc/scheduled_notification_school_windows"
            assert payload["target_mode"] == "teacher"
            return [
                {
                    "school_id": SCHOOL_ID,
                    "timezone": "America/Chicago",
                    "week_start": "2026-08-10",
                }
            ]

    now = datetime(2026, 8, 14, 19, 2, tzinfo=UTC)
    windows = worker._dispatch_windows(FakeClient(), mode="teacher", now=now)  # type: ignore[arg-type]
    assert windows == (
        worker.SchoolDispatchWindow(
            school_id=SCHOOL_ID,
            timezone="America/Chicago",
            week_start=datetime(2026, 8, 10).date(),
        ),
    )


def test_worker_rejects_any_sender_other_than_locked_tpp_address() -> None:
    settings = Settings(ses_from_email="other@planner.guidedscholar.ai")
    with pytest.raises(worker.ScheduledDigestWorkerError, match="approved TPP address"):
        worker.run_teacher_friday_reminders(settings)


def test_teacher_reminder_is_class_specific_and_content_minimized() -> None:
    body = teacher_friday_reminder_text(
        display_name="Teacher Example",
        week_start=datetime(2026, 8, 10).date(),
        next_week_start=datetime(2026, 8, 17).date(),
        items=(
            FridayTeacherReminderItem("English 10", True, False),
            FridayTeacherReminderItem("English 11", False, True),
        ),
        public_base_url="https://planner.guidedscholar.ai",
    )
    assert "English 10" in body
    assert "reflection / completed packet" in body
    assert "English 11" in body
    assert "next week's lesson plan" in body
    assert "student information" in body
    assert "reflection text" not in body.lower()


def test_admin_digest_compares_current_closeout_with_following_week_plans() -> None:
    body = friday_admin_digest_text(
        FridayAdminDigestMetrics(
            week_start=datetime(2026, 8, 10).date(),
            next_week_start=datetime(2026, 8, 17).date(),
            current_teachers_expected=40,
            current_teachers_complete=36,
            current_packets_expected=48,
            current_packets_submitted=44,
            next_teachers_expected=40,
            next_teachers_complete=34,
            next_plans_expected=48,
            next_plans_submitted=42,
            teachers_with_completed_packets=36,
        ),
        public_base_url="https://planner.guidedscholar.ai",
    )
    assert "36 of 40" in body
    assert "44 of 48" in body
    assert "34 of 40" in body
    assert "42 of 48" in body
    assert "Teacher Example" not in body
    assert "teacher-quality" in body


def test_teacher_worker_sends_only_claimed_outstanding_courses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        ses_from_email=APPROVED_SES_FROM_EMAIL,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-placeholder",
        allowed_email_domains="anniston.k12.al.us",
    )
    candidate: dict[str, Any] = {
        "delivery_id": "claim-1",
        "school_id": SCHOOL_ID,
        "recipient_email": "teacher@anniston.k12.al.us",
        "recipient_display_name": "Teacher Example",
        "outstanding_items": [
            {
                "course_name": "Course Six",
                "missing_current_closeout": False,
                "missing_next_plan": True,
            }
        ],
    }
    sent: list[tuple[str, str]] = []
    completions: list[tuple[str, bool]] = []
    fake_client = object()
    week_start = datetime(2026, 8, 10).date()

    def fake_send(
        _settings: Settings,
        *,
        recipient_email: str,
        display_name: str,
        week_start: object,
        next_week_start: object,
        items: tuple[FridayTeacherReminderItem, ...],
    ) -> str:
        del display_name, week_start, next_week_start
        sent.append((recipient_email, items[0].course_name))
        return "message-id-not-retained"

    monkeypatch.setattr(worker, "_service_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        worker,
        "_dispatch_windows",
        lambda _client, *, mode, now: (
            worker.SchoolDispatchWindow(
                school_id=SCHOOL_ID,
                timezone="America/Chicago",
                week_start=week_start,
            ),
        ),
    )
    monkeypatch.setattr(
        worker,
        "_claim_teacher_candidates",
        lambda _client, *, school_id, week_start: [candidate],
    )
    monkeypatch.setattr(worker, "send_teacher_friday_reminder", fake_send)
    monkeypatch.setattr(
        worker,
        "_complete_delivery",
        lambda _client, *, delivery_id, success: completions.append(
            (delivery_id, success)
        ),
    )

    result = worker.run_teacher_friday_reminders(
        settings,
        now=datetime(2026, 8, 14, 19, 0, tzinfo=UTC),
    )

    assert sent == [("teacher@anniston.k12.al.us", "Course Six")]
    assert completions == [("claim-1", True)]
    assert result["school_windows"] == 1
    assert result["sent"] == 1
    assert result["failed"] == 0


def test_teacher_worker_logs_only_aggregate_ses_failure_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = Settings(
        ses_from_email=APPROVED_SES_FROM_EMAIL,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-placeholder",
        allowed_email_domains="anniston.k12.al.us",
    )
    candidate: dict[str, Any] = {
        "delivery_id": "claim-1",
        "school_id": SCHOOL_ID,
        "recipient_email": "teacher@anniston.k12.al.us",
        "recipient_display_name": "Teacher Example",
        "outstanding_items": [
            {
                "course_name": "Course Six",
                "missing_current_closeout": False,
                "missing_next_plan": True,
            }
        ],
    }
    fake_client = object()
    week_start = datetime(2026, 8, 10).date()

    monkeypatch.setattr(worker, "_service_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        worker,
        "_dispatch_windows",
        lambda _client, *, mode, now: (
            worker.SchoolDispatchWindow(
                school_id=SCHOOL_ID,
                timezone="America/Chicago",
                week_start=week_start,
            ),
        ),
    )
    monkeypatch.setattr(
        worker,
        "_claim_teacher_candidates",
        lambda _client, *, school_id, week_start: [candidate],
    )
    monkeypatch.setattr(
        worker,
        "send_teacher_friday_reminder",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            worker.SesDeliveryError(
                "bounded delivery failure",
                provider_code="AccessDeniedException",
            )
        ),
    )
    monkeypatch.setattr(worker, "_complete_delivery", lambda *args, **kwargs: None)

    result = worker.run_teacher_friday_reminders(
        settings,
        now=datetime(2026, 8, 14, 19, 0, tzinfo=UTC),
    )
    output = capsys.readouterr().out

    assert result["failed"] == 1
    assert "candidate_data_failed=0" in output
    assert "ses_failure_codes=AccessDeniedException:1" in output
    assert "teacher@anniston.k12.al.us" not in output
    assert "Teacher Example" not in output
    assert "Course Six" not in output


def test_delivery_ledger_becomes_school_scoped_and_content_minimized() -> None:
    foundation = DELIVERY_MIGRATION.read_text(encoding="utf-8")
    multi_school = MULTI_SCHOOL_MIGRATION.read_text(encoding="utf-8")
    table_definition = foundation.split(
        "create table public.scheduled_notification_deliveries",
        maxsplit=1,
    )[1].split("create index", maxsplit=1)[0]
    assert "teacher_friday_reminder" in table_definition
    assert "admin_weekly_digest" in table_definition
    assert "recipient_profile_id uuid" in table_definition
    assert "recipient_email" not in table_definition
    assert "course_name" not in table_definition
    assert "unique (notification_key, recipient_profile_id, week_start)" in foundation
    assert (
        "unique (notification_key, school_id, recipient_profile_id, week_start)"
        in multi_school
    )
    assert "school_notification_settings" in multi_school
    assert "teacher_reminders_enabled boolean not null default false" in multi_school
    assert "admin_digest_enabled boolean not null default false" in multi_school
    assert "scheduled_notification_school_windows" in multi_school
    assert "target_school_id uuid" in multi_school
    assert "<> 'service_role'" in multi_school


def test_teacher_and_admin_claims_use_named_school_scoped_conflict_constraint() -> None:
    multi_school = MULTI_SCHOOL_MIGRATION.read_text(encoding="utf-8")
    repair = CLAIM_CONFLICT_REPAIR_MIGRATION.read_text(encoding="utf-8")
    named_target = (
        "on conflict on constraint "
        "scheduled_notification_deliveries_school_recipient_week_key"
    )

    assert multi_school.count(named_target) == 2
    assert "on conflict (\n      notification_key,\n      school_id" not in multi_school
    assert "claim_teacher_friday_reminder_candidates(uuid,date)" in repair
    assert "claim_scheduled_admin_weekly_digest_candidates(uuid,date)" in repair
    assert "pg_get_functiondef" in repair
    assert "if repaired_definition = current_definition" in repair
    assert named_target in repair


def test_initial_school_local_window_sql_is_executable_before_hardening() -> None:
    source = MULTI_SCHOOL_MIGRATION.read_text(encoding="utf-8")
    assert "target_now at time zone s.timezone" in source
    assert "lc.local_now::date + lc.teacher_reminder_local_time" in source
    assert "lc.local_now::date + lc.admin_digest_local_time" in source
    assert "date_trunc('day', lc.local_now) +" not in source


def test_school_local_windows_are_iana_and_quarter_hour_governed() -> None:
    source = WINDOW_HARDENING_MIGRATION.read_text(encoding="utf-8")
    assert "teacher_reminder_local_time" in source
    assert "admin_digest_local_time" in source
    assert "mod(extract(minute" in source
    assert "target_now at time zone s.timezone" in source
    assert "extract(isodow from lc.local_now) = 5" in source
    assert "interval '15 minutes'" in source


def test_status_migration_is_separate_from_scheduled_delivery_activation() -> None:
    status = STATUS_MIGRATION.read_text(encoding="utf-8")
    delivery = DELIVERY_MIGRATION.read_text(encoding="utf-8")
    assert "teacher_friday_submission_status" in status
    assert "admin_friday_submission_status" in status
    assert "scheduled_notification_deliveries" not in status
    assert "scheduled_notification_deliveries" in delivery


def test_scheduled_tasks_are_isolated_from_interactive_web_credentials() -> None:
    scheduled = SCHEDULED_STACK.read_text(encoding="utf-8")
    main = MAIN_STACK.read_text(encoding="utf-8")
    assert "TPP_SUPABASE_SERVICE_ROLE_KEY" in scheduled
    assert "TPP_SUPABASE_URL" in scheduled
    assert "TPP_SUPABASE_ANON_KEY" not in scheduled
    assert "TPP_OPENAI_API_KEY" not in scheduled
    assert "TPP_SUPABASE_SERVICE_ROLE_KEY" not in main
    assert "ReadonlyRootFilesystem: true" in scheduled
    assert "Action: ses:SendEmail" in scheduled
    assert "Resource: !Ref SesIdentityArn" in scheduled


def test_dispatchers_are_fixed_but_delivery_time_is_school_local() -> None:
    stack = SCHEDULED_STACK.read_text(encoding="utf-8")
    workflow = ACTIVATION_WORKFLOW.read_text(encoding="utf-8")
    for source in (stack, workflow):
        assert "cron(0/15 * ? * * *)" in source
        assert "UTC" in source
    assert "tpp-pilot-teacher-friday-reminder" in stack
    assert "tpp-pilot-admin-weekly-digest" in stack
    assert "app.scheduled_digest_worker" in stack
    assert "- teacher" in stack
    assert "- admin" in stack
    assert "TPP_SCHEDULED_DIGEST_TIMEZONE" not in stack
    assert "configured local Friday window" in workflow
    assert "New-school notification default: disabled" in workflow
    assert "ScheduleState=DISABLED" in workflow
    assert "ScheduleState=ENABLED" in workflow
    assert "aws ecs run-task" not in workflow.lower()
    assert "send-email" not in workflow.lower()
    assert "immediate/test email sent by this workflow: no" in workflow.lower()


def test_deployment_policies_remain_limited_to_both_exact_dispatchers() -> None:
    cfn = CFN_POLICY.read_text(encoding="utf-8")
    oidc = OIDC_POLICY.read_text(encoding="utf-8")
    for source in (cfn, oidc):
        assert "schedule/default/tpp-pilot-teacher-friday-reminder" in source
        assert "schedule/default/tpp-pilot-admin-weekly-digest" in source
    assert "tpp-pilot-scheduled-digest-task" in cfn
    assert "tpp-pilot-scheduled-digest-task-execution" in cfn
    assert "tpp-pilot-scheduled-digest-scheduler" in cfn


def test_normal_frontend_no_longer_mounts_manual_admin_email_control() -> None:
    source = MAIN_FRONTEND.read_text(encoding="utf-8")
    assert "AdminWeeklyDigestAction" not in source
    assert "FridayStatusExperience" in source
