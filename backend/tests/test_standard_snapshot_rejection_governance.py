from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
REJECTION_GOVERNANCE = (
    MIGRATIONS / "20260810235500_reject_nonselected_pending_standard_snapshots.sql"
)


def test_approval_rejects_only_other_pending_candidates_for_same_source() -> None:
    migration = REJECTION_GOVERNANCE.read_text(encoding="utf-8")

    assert "where ss.source_id = target_source_id" in migration
    assert "and ss.status = 'pending'" in migration
    assert "and ss.id <> target_snapshot_id" in migration
    assert "for update" in migration
    assert "set status = 'rejected'" in migration
    assert "reject_nonselected_standard_snapshot" in migration
    assert "'selected_snapshot_id', target_snapshot_id" in migration


def test_rejected_candidate_is_preserved_as_auditable_history() -> None:
    migration = REJECTION_GOVERNANCE.read_text(encoding="utf-8")

    assert "insert into public.audit_events" in migration
    assert "'standard_snapshot'" in migration
    assert "'status', 'rejected'" in migration
    assert "delete from public.standard_snapshots" not in migration


def test_selected_snapshot_still_uses_existing_explicit_approval_contract() -> None:
    migration = REJECTION_GOVERNANCE.read_text(encoding="utf-8")

    assert "platform administrator role is required" in migration
    assert "only a pending standards snapshot can be approved" in migration
    assert "only a successfully parsed source snapshot can be approved" in migration
    assert "set status = 'superseded'" in migration
    assert "set status = 'approved'" in migration
    assert "approved_snapshot_id = target_snapshot_id" in migration
    assert "private.sync_approved_standard_source_to_catalog" in migration
    assert "grant execute on function public.approve_standard_snapshot(uuid)" in migration
