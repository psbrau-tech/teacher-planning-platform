from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
MIGRATIONS = ROOT / "supabase" / "migrations"
FRONTEND = ROOT / "frontend" / "src"
client = TestClient(app)


def test_monday_helper_rejects_non_monday_week_start() -> None:
    # The draft endpoint reaches the week invariant before storage access.
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


def test_teacher_curriculum_list_is_explicitly_owner_scoped() -> None:
    source = (APP / "curriculum_api.py").read_text(encoding="utf-8")

    list_block = source.split('@router.get("", response_model=list[CurriculumRead])', 1)[1].split(
        '@router.post("", response_model=CurriculumRead', 1
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
    assert "weekly_plan_submissions" not in api  # API may not bypass the governed RPC.
    assert "rpc/teacher_completed_weekly_submission_document" in api
    assert "generate_anniston_hqi_packet" in api


def test_help_and_excel_import_explain_persistence_boundary() -> None:
    help_source = (FRONTEND / "HelpPage.tsx").read_text(encoding="utf-8")
    pacing = (FRONTEND / "PacingSequenceEditor.tsx").read_text(encoding="utf-8")
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")

    assert "Loading Excel reads the workbook into the lesson editor" in help_source
    assert "Nothing is saved merely by selecting the file" in help_source
    assert "loaded from Excel. Review the lesson cards, then save Curriculum & Pacing" in pacing
    assert "Upload, review, then save" in setup
    assert "Nothing is saved until you select" in setup
