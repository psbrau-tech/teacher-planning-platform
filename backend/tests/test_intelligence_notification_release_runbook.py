from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = (
    ROOT
    / "docs"
    / "governance"
    / "INTELLIGENCE_NOTIFICATION_CONTROLLED_RELEASE_RUNBOOK_2026-08-14.md"
)


def normalized() -> str:
    return " ".join(RUNBOOK.read_text(encoding="utf-8").lower().split())


def test_runbook_preserves_reflection_and_student_data_boundaries() -> None:
    source = normalized()
    assert (
        "12 required weekly reflection / plc discussion responses remain teacher-authored"
        in source
    )
    assert "student pii" in source
    assert "student assessment results" in source
    assert (
        "reflection intelligence operates only after teacher-authored reflection submission"
        in source
    )
    assert "not teacher-performance/compliance measures" in source


def test_runbook_keeps_email_fail_closed_until_separate_activation() -> None:
    source = normalized()
    assert "notifications@planner.guidedscholar.ai" in source
    assert "enable tpp ses notifications" in source
    assert "activation workflow itself sends **no test email**" in source
    assert "email must never contain student information" in source
    assert "ses messageid" in source
    assert (
        "adding a school or professional account does not automatically enable scheduled email"
        in source
    )


def test_runbook_keeps_service_role_out_of_interactive_web_task() -> None:
    source = normalized()
    assert (
        "interactive web ecs task must not receive a supabase service-role credential"
        in source
    )
    assert "tpp/pilot/supabase-service-role-key-*" in source
    assert (
        "scheduled worker receives only `tpp_supabase_url` and "
        "`tpp_supabase_service_role_key`"
        in source
    )
    assert "does not receive the openai key, supabase anon key, or oauth secrets" in source


def test_runbook_locks_school_local_friday_delivery_behavior() -> None:
    source = normalized()
    assert "friday at **2:00 pm local time**" in source
    assert "friday at **3:30 pm local time**" in source
    assert "america/chicago" in source
    assert "stored independently on each school" in source
    assert "90-minute courtesy window" in source
    assert "exact professional class/course" in source
    assert "new schools default" in source
    assert "teacher reminders **disabled**" in source
    assert "administrator digests **disabled**" in source


def test_runbook_uses_quarter_hour_dispatchers_but_school_scoped_claims() -> None:
    source = normalized()
    assert "cron(0/15 * ? * * *)" in source
    assert "dispatcher timezone: `utc`" in source
    assert "school's iana timezone" in source
    assert "exact `school_id`" in source
    assert "school-scoped at-most-once delivery keys" in source
    assert "does not mean an email is sent every 15 minutes" in source


def test_runbook_splits_dashboard_and_notification_migration_chain() -> None:
    source = normalized()
    assert "20260815011000_friday_submission_status.sql" in source
    assert "20260815013000_scheduled_friday_notifications.sql" in source
    assert "20260815215500_multi_school_notification_controls.sql" in source
    assert "20260815220500_harden_school_local_notification_windows.sql" in source
    assert "must remain unapplied" in source
    assert "target-scoped database workflow" in source


def test_runbook_requires_exact_release_evidence_and_manual_stop_conditions() -> None:
    source = normalized()
    assert "exact accepted `main` sha" in source
    assert "exact immutable image digest" in source
    assert "live migration head" in source
    assert "ses identity/dns verification" in source
    assert "applying live database migrations" in source
    assert "enabling notifications for a school for the first time" in source
    assert "running the friday notification activation workflow" in source
