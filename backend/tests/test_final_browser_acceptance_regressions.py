import base64
import io
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
BACKEND = ROOT / "backend" / "app"


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


def test_admin_submitted_plan_opens_combined_pdf_with_download_and_print() -> None:
    api = (BACKEND / "administration_api.py").read_text(encoding="utf-8")
    panel = (FRONTEND / "AdminSubmissionPanel.tsx").read_text(encoding="utf-8")
    assert '@router.get("/submissions/{assignment_id}/packet")' in api
    assert "generate_anniston_hqi_packet(submitted.source_data)" in api
    assert 'media_type="application/pdf"' in api
    assert "submitted_revision" in api
    assert "/packet?week_start=" in panel
    assert "Submitted Combined packet PDF" in panel
    assert "Download PDF" in panel
    assert ">Print<" in panel
    assert "Object.entries(selectedPlan.source_data)" not in panel


def test_admin_bulk_review_supports_multiple_teachers_and_submitted_plans() -> None:
    api = (BACKEND / "administration_api.py").read_text(encoding="utf-8")
    panel = (FRONTEND / "AdminSubmissionPanel.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "AdminSubmissionPanel.css").read_text(encoding="utf-8")
    assert 'class BatchSubmissionPacketRequest(BaseModel)' in api
    assert '@router.post("/submissions/batch-packet")' in api
    assert "PdfWriter()" in api
    assert "A maximum of 300 submitted plans" in api
    assert "selectedTeacherIds" in panel
    assert "Select all filtered submitted plans" in panel
    assert "Review selected PDFs" in panel
    assert "Download selected PDF" in panel
    assert "/submissions/batch-packet" in panel
    assert ".teacher-multi-filter" in styles
    assert ".bulk-review-bar" in styles


def test_help_page_covers_teacher_admin_and_data_boundary() -> None:
    help_source = (FRONTEND / "HelpPage.tsx").read_text(encoding="utf-8")
    main_source = (FRONTEND / "main.tsx").read_text(encoding="utf-8")
    assert '=== "/help"' in main_source
    assert "Teacher weekly workflow" in help_source
    assert "Administrator workflow" in help_source
    assert "Weekly Reflection / PLC Discussion" in help_source
    assert "Do not enter student names" in help_source
    assert "AI does not replace teacher judgment" in help_source
    assert "Review selected PDFs" in help_source
