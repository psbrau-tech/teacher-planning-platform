import base64
import io
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
BACKEND = ROOT / "backend" / "app"
MIGRATIONS = ROOT / "supabase" / "migrations"


def test_final_weekly_plan_controls_match_browser_acceptance() -> None:
    shell = (FRONTEND / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")
    assert "hasSavedStandards={savedStandardsCount > 0}" in shell
    assert "onSelectionSaved=" in shell
    assert "Selected authoritative standards" in shell
    assert 'readOnly aria-readonly="true"' in shell
    assert "Next: Review PDFs" not in shell
    assert "pdf-modal-backdrop" in shell
    assert 'window.open("", "_blank")' not in shell
    assert "toast-alert" in shell
    assert "Submit Friday closeout & plan next week" in shell
    assert "Submit weekly plan" in shell


def test_standards_selection_stays_stable_and_filters_stale_catalog_ids() -> None:
    source = (FRONTEND / "StandardsPanel.tsx").read_text(encoding="utf-8")
    assert "const validIds = new Set(body.standards.map" in source
    assert "body.selected_entry_ids.filter((id) => validIds.has(id))" in source
    assert "Array.from(selected).filter((id) => validIds.has(id))" in source
    assert "selectedEntries.length} selected" in source
    assert "resolvedCallback = useRef(onSelectionResolved)" in source
    assert "savedCallback = useRef(onSelectionSaved)" in source
    assert "resolvedCallback.current?.(savedEntries)" in source
    assert "savedCallback.current?.(savedEntries)" in source
    assert "}, [accessToken, assignmentId, weekStart]);" in source


def test_pacing_template_is_a_valid_excel_package_and_redundant_family_is_hidden() -> None:
    course_setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")
    template = (FRONTEND / "pacingTemplate.ts").read_text(encoding="utf-8")
    styles = (FRONTEND / "workflow-overrides.css").read_text(encoding="utf-8")
    assert "Download Excel pacing template" in course_setup
    assert "tpp-curriculum-pacing-template.xlsx" in template
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in template
    encoded = re.search(r'PACING_TEMPLATE_BASE64 = "([A-Za-z0-9+/=]+)"', template)
    assert encoded is not None
    workbook_bytes = base64.b64decode(encoded.group(1), validate=True)
    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as workbook:
        names = set(workbook.namelist())
    assert "[Content_Types].xml" in names
    assert "xl/workbook.xml" in names
    assert "xl/worksheets/sheet1.xml" in names
    assert 'label:has(select[name="standards_family"])' in styles
    assert "Pacing sequence — Unit | Lesson | Standards | Learning targets" in styles


def test_platform_governance_shows_snapshot_date_not_uuid() -> None:
    api_source = (BACKEND / "standards_admin_api.py").read_text(encoding="utf-8")
    panel_source = (FRONTEND / "StandardsAdministrationPanel.tsx").read_text(encoding="utf-8")
    assert "approved_snapshot_retrieved_at" in api_source
    assert '"standard_snapshots"' in api_source
    assert "approved_snapshot_retrieved_at" in panel_source
    assert "approved_snapshot_id ??" not in panel_source


def test_teacher_boundary_banner_and_admin_cleanup_are_present() -> None:
    shell = (FRONTEND / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")
    admin = (FRONTEND / "AdministrationOverview.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "workflow-overrides.css").read_text(encoding="utf-8")
    assert "Teacher and curriculum data only. Use class- or group-level" in shell
    assert ".boundary-strip" in styles
    assert "#8f2029" in styles
    assert "font-weight: 800" in styles
    assert "Access boundary" not in admin
    assert "report-period-control" in admin


def test_submission_schema_distinguishes_plan_and_completed_packet() -> None:
    migration = (
        MIGRATIONS / "20260810003200_distinguish_weekly_plan_and_completed_packet_submissions.sql"
    ).read_text(encoding="utf-8")
    weekly_api = (BACKEND / "weekly_draft_api.py").read_text(encoding="utf-8")
    assert "submission_kind" in migration
    assert "lesson_plan" in migration
    assert "completed_packet" in migration
    assert "submit_weekly_plan_typed" in migration
    assert "admin_weekly_submission_status_v2" in migration
    assert "admin_weekly_submission_document_by_kind" in migration
    assert '"rpc/submit_weekly_plan_typed"' in weekly_api
    assert "_reflection_complete" in weekly_api
    assert "SupabaseFridayValidationStore" in weekly_api


def test_admin_separates_upcoming_lesson_plan_and_completed_packet() -> None:
    api = (BACKEND / "administration_api.py").read_text(encoding="utf-8")
    panel = (FRONTEND / "AdminSubmissionPanel.tsx").read_text(encoding="utf-8")
    document_service = (BACKEND / "document_service.py").read_text(encoding="utf-8")
    assert "generate_anniston_lesson_plan_packet" in document_service
    assert "HqiDocument.INSTRUCTIONAL_FRAMEWORK" in document_service
    assert "HqiDocument.WEEK_AT_A_GLANCE" in document_service
    assert '@router.get("/submissions/{assignment_id}/lesson-plan-packet")' in api
    assert '@router.get("/submissions/{assignment_id}/completed-packet")' in api
    assert "lesson_plan_revision" in panel
    assert "completed_packet_revision" in panel
    assert "Upcoming lesson plan" in panel
    assert "Completed weekly packet" in panel
    assert "View lesson plan" in panel
    assert "View completed packet" in panel


def test_admin_bulk_review_supports_multiple_teachers_and_both_submission_types() -> None:
    api = (BACKEND / "administration_api.py").read_text(encoding="utf-8")
    panel = (FRONTEND / "AdminSubmissionPanel.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "AdminSubmissionPanel.css").read_text(encoding="utf-8")
    assert "submission_kind: SubmissionKind" in api
    assert '@router.post("/submissions/batch-packet")' in api
    assert "PdfWriter()" in api
    assert "A maximum of 300 submitted plans" in api
    assert "selectedTeacherIds" in panel
    assert "Upcoming lesson plans" in panel
    assert "Completed weekly packets" in panel
    assert "Review selected PDFs" in panel
    assert "Download selected PDF" in panel
    assert "/submissions/batch-packet" in panel
    assert ".teacher-multi-filter" in styles
    assert ".bulk-review-bar" in styles
    assert ".submission-mode-bar" in styles


def test_help_page_covers_separate_first_week_friday_and_admin_records() -> None:
    help_source = (FRONTEND / "HelpPage.tsx").read_text(encoding="utf-8")
    main_source = (FRONTEND / "main.tsx").read_text(encoding="utf-8")
    assert '=== "/help"' in main_source
    assert "First week" in help_source
    assert "Every Friday after the first week" in help_source
    assert "The reflection belongs to the week that was just taught" in help_source
    assert "completed packet" in help_source
    assert "following week's lesson plan" in help_source
    assert "Upcoming lesson plan" in help_source
    assert "Completed weekly packet" in help_source
    assert "Administrator workflow" in help_source
    assert "Weekly Reflection / PLC Discussion" in help_source
    assert "Do not enter student names" in help_source
    assert "Review many records" in help_source
