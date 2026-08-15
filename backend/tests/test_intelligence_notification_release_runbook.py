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

    assert "12 required weekly reflection / plc discussion responses remain teacher-authored" in source
    assert "student pii" in source
    assert "student assessment results" in source
    assert "reflection intelligence operates only after teacher-authored reflection submission" in source
    assert "not teacher-performance/compliance measures" in source


def test_runbook_keeps_email_fail_closed_until_separate_activation() -> None:
    source = normalized()

    assert "notifications@planner.guidedscholar.ai" in source
    assert "email still disabled" in source
    assert "activation workflow itself sends no test email" in source
    assert "recipient is the authenticated administrator's own governed professional address" in source
    assert "no arbitrary-recipient field" in source
    assert "ses messageid" in source


def test_runbook_keeps_service_role_out_of_interactive_web_task() -> None:
    source = normalized()

    assert "interactive web ecs task must not receive a supabase service-role credential" in source
    assert "dedicated aws secrets manager secret" in source
    assert "scheduled worker receives only `tpp_supabase_url` and `tpp_supabase_service_role_key`" in source
    assert "does not receive the openai key, supabase anon key, or oauth secrets" in source


def test_runbook_does_not_invent_automatic_delivery_time() -> None:
    source = normalized()

    assert "automatic delivery has **no approved clock time yet**" in source
    assert "exact schedule expression must be supplied and explicitly approved" in source
    assert "america/chicago" in source
    assert "weeks with no instruction" in source


def test_runbook_requires_exact_release_evidence_and_manual_stop_conditions() -> None:
    source = normalized()

    assert "exact `main` commit sha" in source
    assert "exact immutable image digest" in source
    assert "current supabase migration head actually applied" in source
    assert "ses identity/dns verification" in source
    assert "applying database migrations" in source
    assert "running either email activation workflow" in source
    assert "sending the first live/pilot email acceptance message" in source
