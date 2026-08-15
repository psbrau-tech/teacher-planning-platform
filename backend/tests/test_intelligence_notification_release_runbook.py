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


def test_runbook_locks_teacher_and_admin_friday_schedule() -> None:
    source = normalized()
    assert "friday at **2:00 pm local time**" in source
    assert "cron(0 14 ? * fri *)" in source
    assert "friday at **3:30 pm local time**" in source
    assert "cron(30 15 ? * fri *)" in source
    assert "america/chicago" in source
    assert "90-minute courtesy window" in source
    assert "exact professional class/course" in source


def test_runbook_splits_dashboard_and_scheduled_delivery_migrations() -> None:
    source = normalized()
    assert "20260815011000_friday_submission_status.sql" in source
    assert "20260815013000_scheduled_friday_notifications.sql" in source
    assert "must remain deferred" in source
    assert "target-scoped database workflow" in source


def test_runbook_requires_exact_release_evidence_and_manual_stop_conditions() -> None:
    source = normalized()
    assert "exact `main` commit sha" in source
    assert "exact immutable image digest" in source
    assert "live migration head" in source
    assert "ses identity/dns verification" in source
    assert "applying live database migrations" in source
    assert "running the friday notification activation workflow" in source
