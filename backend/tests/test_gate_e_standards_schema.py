from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
SCHEMA = MIGRATIONS / "20260807195500_gate_e_standards_snapshots.sql"
INVARIANTS = MIGRATIONS / "20260807195600_gate_e_standards_invariants.sql"
LOGICAL_KEYS = MIGRATIONS / "20260807200400_standard_source_logical_keys.sql"
SOURCE_ROLES = MIGRATIONS / "20260807200500_standard_source_roles.sql"
APPROVAL = MIGRATIONS / "20260807200600_snapshot_course_manifests_and_approval.sql"


def test_gate_e_schema_has_governed_snapshot_model() -> None:
    source = SCHEMA.read_text(encoding="utf-8")

    for table in (
        "public.standard_sources",
        "public.standard_snapshots",
        "public.standard_courses",
        "public.standard_entries",
        "public.assignment_standard_courses",
        "public.weekly_standard_selections",
        "public.standard_source_checks",
    ):
        assert f"create table {table}" in source
        assert f"alter table {table} enable row level security;" in source

    assert "status in ('pending', 'approved', 'superseded', 'rejected')" in source
    assert "result_status in ('unchanged', 'changed', 'unavailable_error')" in source
    assert "standard_snapshots_one_approved_per_source" in source
    assert "ss.status = 'approved'" in source


def test_initial_source_seeds_are_bootstrap_not_catalog_boundary() -> None:
    source = SCHEMA.read_text(encoding="utf-8")
    logical = LOGICAL_KEYS.read_text(encoding="utf-8")

    # Initial seeds allow deterministic migration/bootstrap testing, but later migrations
    # normalize stable logical keys and catalog discovery expands beyond these fixtures.
    assert "'alabama_ela_2021'" in source
    assert "'alabama_bma_2021'" in source
    assert "'army_jrotc_v12'" in source
    assert "alabama_academic_english_language_arts" in logical
    assert "alabama_cte_cos_business_management_administration" in logical

    # Authoritative standard text is populated by deterministic import, not copied into
    # a migration or synthesized by AI.
    assert "insert into public.standard_entries" not in source


def test_teacher_writes_cannot_activate_or_replace_snapshots() -> None:
    source = SCHEMA.read_text(encoding="utf-8")

    assert "public.standard_snapshots" in source
    assert "to service_role;" in source
    authenticated_grant = source.split(
        "grant insert, update, delete on table\n  public.assignment_standard_courses",
        maxsplit=1,
    )[1].split("to authenticated;", maxsplit=1)[0]
    assert "public.standard_snapshots" not in authenticated_grant


def test_cross_source_invariants_remain_enforced() -> None:
    source = INVARIANTS.read_text(encoding="utf-8")

    assert "private.enforce_standard_entry_source" in source
    assert "snapshot_source_id <> course_source_id" in source
    assert "private.enforce_approved_standard_snapshot_pointer" in source
    assert "snapshot_source_id <> new.id" in source
    assert "snapshot_status <> 'approved'" in source


def test_pending_courses_do_not_project_until_exact_snapshot_approval() -> None:
    source = APPROVAL.read_text(encoding="utf-8")

    assert "drop trigger if exists standard_course_catalog_sync_trigger" in source
    assert "create table public.standard_snapshot_courses" in source
    assert "private.enforce_snapshot_course_source" in source
    assert "private.sync_approved_standard_source_to_catalog" in source
    assert "catalog projection requires an approved snapshot for this source" in source
    assert "ssc.snapshot_id = target_snapshot_id" in source
    assert "perform private.sync_approved_standard_source_to_catalog" in source


def test_snapshot_approval_supports_standards_and_listing_only_sources() -> None:
    source = APPROVAL.read_text(encoding="utf-8")
    roles = SOURCE_ROLES.read_text(encoding="utf-8")

    assert "src.provides_standard_entries" in roles
    assert "source_kind <> 'program_guide' or not provides_standard_entries" in roles
    assert "target_parser_status <> 'parsed'" in source
    assert "target_course_count = 0" in source
    assert "target_provides_entries and target_entry_count = 0" in source
    assert "not target_provides_entries and target_entry_count <> 0" in source
    assert "all four Army JROTC LET courses are required" in source
    assert "set status = 'superseded'" in source
    assert "set status = 'approved'" in source
    assert "'approve_standard_snapshot'" in source
