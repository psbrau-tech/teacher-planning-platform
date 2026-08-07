from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
SELECTION = MIGRATIONS / "20260807195800_gate_e_standards_selection_rpcs.sql"
CATALOG = MIGRATIONS / "20260807200100_standard_catalog_mapping.sql"
USAGE = MIGRATIONS / "20260807195900_ai_usage_response_and_cache_write.sql"
DECISIONS = MIGRATIONS / "20260807200000_ai_suggestion_decisions.sql"


def test_teacher_maps_assignment_to_one_canonical_catalog_course() -> None:
    source = CATALOG.read_text(encoding="utf-8")

    assert "create table public.standard_catalog_categories" in source
    assert "create table public.standard_catalog_courses" in source
    assert "create table public.standard_catalog_course_sources" in source
    assert "public.set_assignment_standard_catalog_course" in source
    assert "private.has_role('teacher'::public.app_role, null)" in source
    assert "teachers may map only their own teaching assignments" in source
    assert "catalog_course_id" in source
    assert "Subject / Career Cluster and Grade / Course" in source


def test_mapping_change_requires_warning_and_preserves_validated_history() -> None:
    source = CATALOG.read_text(encoding="utf-8")

    assert "weekly_plan_snapshots" in source
    assert "confirm_existing_plans" in source
    assert "standards mapping change requires explicit confirmation" in source
    assert "friday_validation_snapshots" in source
    assert "open_selection_count_cleared" in source
    assert "validated_week_count_preserved" in source
    assert "assignment_standard_course_history" in source
    assert "not exists (" in source
    assert "delete from public.weekly_standard_selections" in source


def test_canonical_course_can_keep_multiple_authoritative_sources() -> None:
    source = CATALOG.read_text(encoding="utf-8")

    assert "standard_catalog_course_sources" in source
    assert "relationship in ('primary', 'supplemental_authority')" in source
    assert "source_course_id" in source
    assert "catalog_course_id" in source


def test_weekly_standard_selection_rpc_is_teacher_scoped_and_atomic() -> None:
    source = CATALOG.read_text(encoding="utf-8")

    assert "public.replace_weekly_standard_selections" in source
    assert "private.has_role('teacher'::public.app_role, null)" in source
    assert "ta.teacher_id = actor_id" in source
    assert "no more than 20 standards may be selected for one week" in source
    assert "ss.status = 'approved'" in source
    assert "sccs.catalog_course_id = mapped_catalog_course_id" in source
    assert "delete from public.weekly_standard_selections" in source
    assert "insert into public.weekly_standard_selections" in source


def test_old_platform_admin_mapping_policy_is_superseded() -> None:
    source = CATALOG.read_text(encoding="utf-8")

    assert "drop policy if exists assignment_standard_courses_platform_admin_write" in source
    assert "revoke insert, update, delete on table public.assignment_standard_courses" in source


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
