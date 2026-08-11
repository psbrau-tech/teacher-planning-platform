from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
MIGRATIONS = ROOT / "supabase" / "migrations"
FRONTEND = ROOT / "frontend" / "src"
client = TestClient(app)


def test_monday_helper_rejects_non_monday_week_start() -> None:
    response = client.get(
        "/api/v1/weekly-drafts",
        headers={"X-TPP-Teacher-ID": "monday-contract-teacher"},
        params={"assignment_id": "assignment-1", "week_start": "2026-08-11"},
    )
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Week of must be a Monday")


def test_monday_invariant_is_applied_to_core_weekly_api_surfaces() -> None:
    live_planning = (APP / "live_planning_api.py").read_text(encoding="utf-8")
    friday = (APP / "friday_validation_api.py").read_text(encoding="utf-8")
    drafts = (APP / "weekly_draft_api.py").read_text(encoding="utf-8")
    schedule = (APP / "schedule_exception_api.py").read_text(encoding="utf-8")

    assert live_planning.count("require_monday(") >= 2
    assert friday.count("require_monday(") >= 2
    assert drafts.count("require_monday(") >= 4
    assert "require_monday(week_start)" in schedule


def test_all_visible_week_selectors_normalize_to_monday() -> None:
    shell = (FRONTEND / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")
    admin = (FRONTEND / "AdminSubmissionPanel.tsx").read_text(encoding="utf-8")

    assert "function mondayForIso(" in shell
    assert "Week of (Monday)" in shell
    assert "Previous week" in shell and "Next week" in shell
    assert 'onChange={(event) => onChange(mondayForIso(event.target.value))}' in shell

    assert "function mondayForIso(" in admin
    assert "Week of (Monday)" in admin
    assert "Previous week" in admin and "Next week" in admin
    assert "setWeekStart(mondayForIso(value))" in admin
    assert 'setWeekStart(event.target.value)' not in admin


def test_database_preserves_one_canonical_monday_week_identity() -> None:
    migration = (
        MIGRATIONS / "20260811030200_enforce_monday_week_start.sql"
    ).read_text(encoding="utf-8")

    for table in (
        "weekly_plan_snapshots",
        "weekly_plan_submissions",
        "friday_validation_snapshots",
        "weekly_standard_selections",
    ):
        assert f"alter table public.{table}" in migration
        assert f"{table}_week_start_monday" in migration
    assert migration.count("check (extract(isodow from week_start) = 1)") == 4


def test_teacher_curriculum_list_is_explicitly_owner_scoped() -> None:
    source = (APP / "curriculum_api.py").read_text(encoding="utf-8")

    list_block = source.split('@router.get("", response_model=list[CurriculumRead])', 1)[1].split(
        '@router.get("/{curriculum_id}"', 1
    )[0]
    assert '"created_by": f"eq.{identity.subject}"' in list_block
    assert '"is_active": "eq.true"' in list_block
    assert "private.can_admin_school" not in list_block
    assert '@router.delete("/{curriculum_id}"' in source
    assert "still attached to an active class" in source
    assert 'payload={"is_active": False}' in source


def test_course_setup_schema_allows_temporary_null_curriculum_only_until_planning() -> None:
    migration = (
        MIGRATIONS / "20260811030000_progressive_course_setup_nullable_curriculum.sql"
    ).read_text(encoding="utf-8")
    planning = (APP / "live_planning_api.py").read_text(encoding="utf-8")

    assert "alter column curriculum_id drop not null" in migration
    assert "A curriculum must be attached before weekly planning" in migration
    assert "def _require_curriculum(" in planning
    assert "Complete Course Setup Step 2" in planning


def test_teacher_completed_packet_is_owned_and_immutable() -> None:
    migration = (
        MIGRATIONS / "20260811030100_teacher_completed_packet_read.sql"
    ).read_text(encoding="utf-8")
    api = (APP / "teacher_submission_api.py").read_text(encoding="utf-8")

    assert "teacher_completed_weekly_submission_document" in migration
    assert "wps.teacher_id = (select auth.uid())" in migration
    assert "wps.submission_kind = 'completed_packet'" in migration
    assert "order by wps.revision desc" in migration
    assert "grant execute" in migration
    assert "weekly_plan_submissions" not in api
    assert "rpc/teacher_completed_weekly_submission_document" in api
    assert "generate_anniston_hqi_packet" in api


def test_help_and_excel_import_explain_persistence_boundary() -> None:
    help_source = (FRONTEND / "HelpPage.tsx").read_text(encoding="utf-8")
    pacing = (FRONTEND / "PacingSequenceEditor.tsx").read_text(encoding="utf-8")
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")

    assert "Upload Excel" in help_source
    assert "reads the workbook into a compact review" in help_source
    assert "Nothing is saved" in help_source
    assert "Save Curriculum & Pacing & Continue" in help_source
    assert "loaded from Excel. Review the sequence below, then save Curriculum & Pacing" in pacing
    assert "Nothing is saved yet" in pacing
    assert "Upload, review, then save" in setup
    assert "Nothing is saved" in setup
    assert "Save Curriculum & Pacing & Continue" in setup
