from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPLY = ROOT / ".github" / "workflows" / "apply-pilot-database.yml"
DEPLOY = ROOT / ".github" / "workflows" / "deploy-pilot.yml"
VERIFY = ROOT / "scripts" / "verify_exact_release_candidate.sh"
STAGE = ROOT / "scripts" / "stage_migrations_through.sh"


def test_database_workflow_is_bound_to_exact_main_and_target_head() -> None:
    source = APPLY.read_text(encoding="utf-8")

    assert "expected_main_sha:" in source
    assert "target_migration_head:" in source
    assert "apply_target_confirmed:" in source
    assert "scripts/verify_exact_release_candidate.sh" in source
    assert "scripts/stage_migrations_through.sh" in source
    assert "Deferred later migrations" in source
    assert source.index("scripts/stage_migrations_through.sh") < source.index("db push --db-url")


def test_database_workflow_cannot_mutate_without_exact_target_confirmation() -> None:
    source = APPLY.read_text(encoding="utf-8")

    assert 'inputs.dry_run_only }}" != "true"' in source
    assert 'inputs.apply_target_confirmed }}" != "true"' in source
    assert "Database mutation is blocked until the exact migration target is approved." in source
    assert "applied only through the approved target" in source


def test_deployment_workflow_requires_exact_candidate_and_applied_head_attestation() -> None:
    source = DEPLOY.read_text(encoding="utf-8")

    assert "expected_main_sha:" in source
    assert "expected_migration_head:" in source
    assert "migration_head_applied_confirmed:" in source
    assert "scripts/verify_exact_release_candidate.sh" in source
    assert "REQUIRE_MIGRATION_APPLIED_CONFIRMATION: 'true'" in source
    assert "MIGRATION_APPLIED_CONFIRMED: ${{ inputs.migration_head_applied_confirmed }}" in source
    assert "Supabase service-role/database/OAuth runtime credentials: \\`not injected\\`" in source


def test_exact_candidate_helper_rejects_branch_sha_and_unknown_migration() -> None:
    source = VERIFY.read_text(encoding="utf-8")

    assert 'GITHUB_REF:-}" != "refs/heads/main"' in source
    assert 'GITHUB_SHA:-}" != "$expected_main_sha"' in source
    assert '-name "${expected_migration_head}_*.sql"' in source
    assert "Expected exactly one repository migration" in source
    assert "confirmed applied" in source


def test_target_staging_defers_only_later_repository_migrations() -> None:
    source = STAGE.read_text(encoding="utf-8")

    assert 'if [[ "$version" > "$target_head" ]]' in source
    assert 'mv "$migration" "$deferred_dir/$file_name"' in source
    assert '"${remaining_head%%_*}" != "$target_head"' in source
    assert "deferred_count=$deferred_count" in source
