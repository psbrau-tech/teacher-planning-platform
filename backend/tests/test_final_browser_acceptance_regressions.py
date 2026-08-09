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


def test_standards_selection_filters_stale_catalog_ids() -> None:
    source = (FRONTEND / "StandardsPanel.tsx").read_text(encoding="utf-8")

    assert "const validIds = new Set(body.standards.map" in source
    assert "body.selected_entry_ids.filter((id) => validIds.has(id))" in source
    assert "Array.from(selected).filter((id) => validIds.has(id))" in source
    assert "selectedEntries.length} selected" in source
    assert "onSelectionSaved?.(savedEntries)" in source


def test_pacing_template_is_a_real_excel_workbook_download() -> None:
    course_setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")
    template = (FRONTEND / "pacingTemplate.ts").read_text(encoding="utf-8")

    assert "Download Excel pacing template" in course_setup
    assert "Select a governed standards family" in course_setup
    assert "tpp-curriculum-pacing-template.xlsx" in template
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in template


def test_platform_governance_shows_snapshot_date_not_uuid() -> None:
    api_source = (BACKEND / "standards_admin_api.py").read_text(encoding="utf-8")
    panel_source = (FRONTEND / "StandardsAdministrationPanel.tsx").read_text(
        encoding="utf-8"
    )

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
