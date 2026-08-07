from pathlib import Path


MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
SCHEMA = MIGRATIONS / "20260807195500_gate_e_standards_snapshots.sql"
INVARIANTS = MIGRATIONS / "20260807195600_gate_e_standards_invariants.sql"


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


def test_authoritative_sources_are_bounded_and_precisely_pinned() -> None:
    source = SCHEMA.read_text(encoding="utf-8")

    assert "'alabama_ela_2021'" in source
    assert "'alabama_bma_2021'" in source
    assert "'army_jrotc_v12'" in source
    assert "JROTC-Curriculum-Guide-25JUN25-4.docx" in source
    assert "2021-Alabama-Course-of-Study-English-Language-Arts_V1.0.pdf" in source
    assert "2021-BMA-Course-of-StudyMARCH2021.pdf" in source

    # Authoritative standard text is populated by deterministic import, not copied into
    # a migration or synthesized by AI.
    assert "insert into public.standard_entries" not in source


def test_teacher_writes_cannot_activate_or_replace_snapshots() -> None:
    source = SCHEMA.read_text(encoding="utf-8")

    assert "grant insert, update, delete on table\n  public.assignment_standard_courses" in source
    assert "public.weekly_standard_selections\n  to authenticated;" in source
    assert "public.standard_snapshots" in source
    assert "to service_role;" in source

    authenticated_grant = source.split(
        "grant insert, update, delete on table\n  public.assignment_standard_courses",
        maxsplit=1,
    )[1].split("to authenticated;", maxsplit=1)[0]
    assert "public.standard_snapshots" not in authenticated_grant


def test_cross_source_and_approval_invariants_are_enforced() -> None:
    source = INVARIANTS.read_text(encoding="utf-8")

    assert "private.enforce_standard_entry_source" in source
    assert "snapshot_source_id <> course_source_id" in source
    assert "private.enforce_approved_standard_snapshot_pointer" in source
    assert "snapshot_source_id <> new.id" in source
    assert "snapshot_status <> 'approved'" in source

    assert "public.approve_standard_snapshot" in source
    assert "private.has_role('platform_admin'::public.app_role, null)" in source
    assert "set status = 'superseded'" in source
    assert "set status = 'approved'" in source
    assert "'approve_standard_snapshot'" in source
