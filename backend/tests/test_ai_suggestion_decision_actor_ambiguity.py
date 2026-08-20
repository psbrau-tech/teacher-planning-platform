from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260820020000_fix_ai_suggestion_decision_actor_ambiguity.sql"
)


def test_ai_suggestion_decision_uses_unambiguous_authenticated_actor() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "requesting_actor_id uuid := (select auth.uid())" in source
    assert "aue.teacher_id = requesting_actor_id" in source
    assert "teacher_id = requesting_actor_id" in source
    assert "requesting_actor_id," in source
    assert "\n  actor_id uuid :=" not in source


def test_ai_suggestion_decision_preserves_teacher_control_and_audit() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "private.has_role('teacher'::public.app_role, null)" in source
    assert "target_decision not in ('accepted', 'edited', 'rejected')" in source
    assert "aue.succeeded = true" in source
    assert "insert into public.ai_suggestion_decisions" in source
    assert "insert into public.audit_events" in source
    assert "grant execute on function public.record_ai_suggestion_decision" in source
    assert "to authenticated" in source
