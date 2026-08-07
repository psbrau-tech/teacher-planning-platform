from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
SELECTION = MIGRATIONS / "20260807195800_gate_e_standards_selection_rpcs.sql"
USAGE = MIGRATIONS / "20260807195900_ai_usage_response_and_cache_write.sql"
DECISIONS = MIGRATIONS / "20260807200000_ai_suggestion_decisions.sql"


def test_assignment_mapping_is_platform_admin_governed() -> None:
    source = SELECTION.read_text(encoding="utf-8")

    assert "drop policy if exists assignment_standard_courses_owner_write" in source
    assert "assignment_standard_courses_platform_admin_write" in source
    assert "private.has_role('platform_admin'::public.app_role, null)" in source
    assert "sc.is_pilot_allowed" in source


def test_weekly_standard_selection_rpc_is_teacher_scoped_and_atomic() -> None:
    source = SELECTION.read_text(encoding="utf-8")

    assert "public.replace_weekly_standard_selections" in source
    assert "private.has_role('teacher'::public.app_role, null)" in source
    assert "private.can_access_assignment(target_assignment_id)" in source
    assert "no more than 20 standards may be selected for one week" in source
    assert "ss.status = 'approved'" in source
    assert "delete from public.weekly_standard_selections" in source
    assert "insert into public.weekly_standard_selections" in source
    assert "replace_weekly_standard_selections" in source


def test_ai_usage_records_provider_response_and_cache_write_tokens() -> None:
    source = USAGE.read_text(encoding="utf-8")

    assert "cache_write_tokens bigint not null default 0" in source
    assert "provider_response_id text" in source
    assert "ai_usage_events_provider_response_idx" in source


def test_teacher_ai_decisions_are_narrow_and_do_not_store_suggestion_text() -> None:
    source = DECISIONS.read_text(encoding="utf-8")

    assert "create table public.ai_suggestion_decisions" in source
    assert "decision in ('accepted', 'edited', 'rejected')" in source
    assert "public.record_ai_suggestion_decision" in source
    assert "private.has_role('teacher'::public.app_role, null)" in source
    assert "aue.teacher_id = actor_id" in source
    assert "accepted_by_teacher" in source
    assert "record_ai_suggestion_decision" in source
    assert "suggestion_text" not in source
