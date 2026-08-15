from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "docs" / "PILOT_DEPLOYMENT.md"
PREFLIGHT = ROOT / "docs" / "PILOT_PREFLIGHT.md"
SECRETS = ROOT / "docs" / "PILOT_SECRETS_AND_DNS.md"


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

    for source in (deployment, preflight, secrets):
        assert "through" in source and "target" in source

    assert "20260815001500" in deployment
    assert "20260815011000_scheduled_admin_digest_worker.sql" in deployment
    assert "20260815001500" in preflight
    assert "20260815011000_scheduled_admin_digest_worker.sql" in preflight


def test_operations_docs_keep_scheduled_service_role_out_of_interactive_task() -> None:
    deployment = normalized(DEPLOYMENT)
    secrets = normalized(SECRETS)

    assert "separate scheduled ecs task" in secrets
    assert "only that isolated worker may receive `tpp_supabase_service_role_key`" in secrets
    assert "scheduled worker is isolated in a separate task" in deployment
    assert "interactive task must not contain `tpp_supabase_service_role_key`" in deployment


def test_operations_docs_do_not_equate_repository_inventory_with_live_db_state() -> None:
    deployment = normalized(DEPLOYMENT)
    preflight = normalized(PREFLIGHT)

    assert "repository source state and live database state are separate evidence" in deployment
    assert "does **not** prove" in preflight
    assert "live pilot database" in preflight
    assert "later intentionally deferred source migration" in deployment
