from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADMIN_API = ROOT / "backend" / "app" / "administration_api.py"
MIGRATION = ROOT / "supabase" / "migrations" / "20260813143000_selected_teacher_admin_reporting.sql"
ADMIN_REPORT = ROOT / "frontend" / "src" / "AdminSelectedTeacherUsageReport.tsx"
ADMIN_PORTAL = ROOT / "frontend" / "src" / "AdminSelectedTeacherUsagePortal.tsx"
OWNER_CSS = ROOT / "frontend" / "src" / "owner-overview.css"
PRODUCT_CSS = ROOT / "frontend" / "src" / "product-owner-dashboard.css"
MAIN = ROOT / "frontend" / "src" / "main.tsx"


def test_admin_usage_can_be_scoped_to_explicit_teacher_ids() -> None:
    api = ADMIN_API.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")
    report = ADMIN_REPORT.read_text(encoding="utf-8")

    assert 'Query(alias="teacher_id")' in api
    assert "rpc/admin_usage_for_period_selected" in api
    assert 'target_teacher_ids' in api
    assert "admin_usage_for_period_selected" in migration
    assert "join selected_teachers st on st.teacher_id = ta.teacher_id" in migration
    assert 'query.append("teacher_id", id)' in report
    assert "No aggregate report is built until at least one teacher is selected" in report


def test_selected_teacher_report_replaces_old_all_teacher_summary() -> None:
    portal = ADMIN_PORTAL.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "src" / "admin-selected-teacher-usage.css").read_text(encoding="utf-8")

    assert "AdminSelectedTeacherUsagePortal" in main
    assert 'aria-label="Administration reporting"' in portal
    assert 'summary[aria-label="School planning usage"]' in css
    assert "admin-selected-usage-slot" in portal


def test_owner_cost_and_time_are_ordered_before_standards_and_metrics_do_not_overlap() -> None:
    owner_css = OWNER_CSS.read_text(encoding="utf-8")
    product_css = PRODUCT_CSS.read_text(encoding="utf-8")

    assert "section:nth-of-type(4) { order: 1; }" in owner_css
    assert ".owner-active-time-breakout { order: 2; }" in owner_css
    assert "section:nth-of-type(3) { order: 5; }" in owner_css
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in product_css
    assert "min-height: 116px" in product_css
    assert ".owner-tool-card .owner-metric small" in product_css
    assert "margin: 0;" in product_css
