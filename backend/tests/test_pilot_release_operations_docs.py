from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "docs" / "PILOT_DEPLOYMENT.md"
PREFLIGHT = ROOT / "docs" / "PILOT_PREFLIGHT.md"
SECRETS = ROOT / "docs" / "PILOT_SECRETS_AND_DNS.md"
BASELINE = ROOT / "docs" / "governance" / "PILOT_BASELINE_2026-08-20.md"


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_operations_docs_describe_current_interactive_runtime_secret_set() -> None:
    deployment = normalized(DEPLOYMENT)
    secrets = normalized(SECRETS)

    for source in (deployment, secrets):
        assert "tpp_supabase_url" in source
        assert "tpp_supabase_anon_key" in source
        assert "tpp_openai_api_key" in source
        assert "supabase service-role" in source

    assert "openai remains reserved for a future reviewed feature" not in secrets
    assert "interactive task must not contain" in deployment
    assert "interactive web task" in secrets


def test_operations_docs_record_exact_accepted_august_20_baseline() -> None:
    deployment = normalized(DEPLOYMENT)
    baseline = normalized(BASELINE)

    for source in (deployment, baseline):
        assert "b33bf905e98012b857c4434039fced08ff89137b" in source
        assert "20260820020000" in source

    assert "new accepted tpp pilot baseline" in baseline
    assert "589 tests" in baseline
    assert "one class day" in baseline
    assert "explicitly accept, edit, or reject" in baseline
    assert "student pii and student education records remain prohibited" in baseline
    assert "does not itself activate ses" in baseline


def test_operations_docs_match_exact_sha_and_target_scoped_migration_workflows() -> None:
    deployment = normalized(DEPLOYMENT)
    preflight = normalized(PREFLIGHT)
    secrets = normalized(SECRETS)

    for source in (deployment, secrets):
        assert "expected_main_sha" in source
        assert "target_migration_head" in source
        assert "dry_run_only=true" in source
        assert "apply_target_confirmed" in source

    assert "exact accepted `main` sha" in preflight
    assert "target_migration_head" in preflight
    assert "dry_run_only=true" in preflight
    assert "apply_target_confirmed" in preflight

    for source in (deployment, preflight):
        assert "through" in source and "target" in source
        assert "b33bf905e98012b857c4434039fced08ff89137b" in source
        assert "20260820020000" in source
        assert "separate" in source

    assert "20260815011000_friday_submission_status.sql" in preflight
    assert "20260815013000_scheduled_friday_notifications.sql" in preflight

    assert "20260815013000_scheduled_friday_notifications.sql" in secrets
    assert "20260815215500_multi_school_notification_controls.sql" in secrets
    assert "20260815220500_harden_school_local_notification_windows.sql" in secrets
    assert "verified live head `20260815220500" in secrets
    assert "notification preparation chain is now applied" in secrets


def test_operations_docs_record_route53_and_governed_reply_to() -> None:
    secrets = normalized(SECRETS)

    assert "authoritative dns in amazon route 53" in secrets
    assert "domain identity is verified" in secrets
    assert "dkim is successful and enabled" in secrets
    assert "production-access request has been submitted" in secrets
    assert "notifications@planner.guidedscholar.ai" in secrets
    assert "peter@brauconsulting.com" in secrets


def test_operations_docs_keep_scheduled_service_role_out_of_interactive_task() -> None:
    deployment = normalized(DEPLOYMENT)
    secrets = normalized(SECRETS)

    assert "separate scheduled one-shot ecs tasks" in secrets
    assert "only those isolated worker tasks may receive `tpp_supabase_service_role_key`" in secrets
    assert "isolated in separate one-shot ecs tasks" in deployment
    assert "interactive task must not contain `tpp_supabase_service_role_key`" in deployment


def test_operations_docs_do_not_equate_repository_inventory_with_live_db_state() -> None:
    deployment = normalized(DEPLOYMENT)
    preflight = normalized(PREFLIGHT)
    secrets = normalized(SECRETS)

    assert "repository source state and live database state are separate evidence" in deployment
    assert "does **not** prove" in preflight
    assert "live pilot database" in preflight
    assert "later intentionally deferred source migration" in deployment
    assert "keep repository source state separate from live database evidence" in secrets
