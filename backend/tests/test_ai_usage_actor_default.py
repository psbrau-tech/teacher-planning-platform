from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTOR_DEFAULT_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260819195500_ai_usage_actor_default.sql"
)
ACTOR_POLICY_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260814190100_ai_usage_actor_policy.sql"
)


def test_authenticated_ai_usage_actor_defaults_without_weakening_rls() -> None:
    default_source = ACTOR_DEFAULT_MIGRATION.read_text(encoding="utf-8")
    policy_source = ACTOR_POLICY_MIGRATION.read_text(encoding="utf-8")

    assert "alter column actor_id set default auth.uid()" in default_source
    assert "actor_id = (select auth.uid())" in policy_source
    assert "teacher_id = (select auth.uid())" in policy_source
    assert "private.has_role('teacher'::public.app_role, school_id)" in policy_source
    assert "actor_id is null" not in policy_source
