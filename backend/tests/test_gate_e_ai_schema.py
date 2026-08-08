from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
SELECTION = MIGRATIONS / "20260807195800_gate_e_standards_selection_rpcs.sql"
CATALOG = MIGRATIONS / "20260807200100_standard_catalog_mapping.sql"
SOURCE_ROLES = MIGRATIONS / "20260807200500_standard_source_roles.sql"
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
    source = SOURCE_ROLES.read_text(encoding="utf-8")

    assert "standard_catalog_course_sources" in source
    assert "relationship in ('primary', 'course_listing', 'supplemental_authority')" in source
    assert "source_course_id" in source
    assert "catalog_course_id" in source


def test_program_guides_are_course_listings_not_standard_entry_sources() -> None:
    source = SOURCE_ROLES.read_text(encoding="utf-8")

    assert "source_kind <> 'program_guide' or not provides_standard_entries" in source
    assert "when source_kind = 'program_guide' then 'course_listing'" in source
    assert "sccs.relationship in ('primary', 'supplemental_authority')" in source
    assert "src.provides_standard_entries" in source


def test_army_curriculum_remains_supplemental_authority() -> None:
    source = SOURCE_ROLES.read_text(encoding="utf-8")

    assert "where source_key = 'army_jrotc_v12'" in source
    assert "source_kind = 'supplemental_curriculum'" in source
    assert "when source_kind = 'supplemental_curriculum' then 'supplemental_authority'" in source


def test_supplemental_source_cannot_rename_existing_canonical_course() -> None:
    source = SOURCE_ROLES.read_text(encoding="utf-8")

    assert "when source_relationship = 'supplemental_authority'" in source
    assert "then public.standard_catalog_courses.display_name" in source
    assert "source_priority" in source
    assert "when 'course_listing' then 5" in source
    assert "when 'primary' then 10" in source


def test_weekly_standard_selection_rpc_is_teacher_scoped_and_atomic() -> None:
    source = SOURCE_ROLES.read_text(encoding="utf-8")

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
