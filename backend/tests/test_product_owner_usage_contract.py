from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase" / "migrations" / "20260812221500_product_owner_usage_telemetry.sql"
API = ROOT / "backend" / "app" / "product_usage_api.py"
MAIN_API = ROOT / "backend" / "app" / "main.py"
OBSERVER = ROOT / "frontend" / "src" / "ProductUsageObserver.tsx"
DASHBOARD = ROOT / "frontend" / "src" / "ProductOwnerDashboardExperience.tsx"
FRONTEND_MAIN = ROOT / "frontend" / "src" / "main.tsx"


def test_product_usage_events_are_bounded_and_content_free() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "create table public.product_usage_events" in source
    assert "event_key text not null" in source
    assert "metadata" not in source.lower()
    assert "source_data" not in source
    assert "teacher-entered planning/reflection text" in source
    assert "student" in source.lower()  # explicit no-student-data comment
    assert "revoke all on table public.product_usage_events" in source
    assert "record_product_usage_event" in source


def test_product_owner_summary_uses_authoritative_records_and_platform_role() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    main = MAIN_API.read_text(encoding="utf-8")

    assert "weekly_plan_snapshots" in source
    assert "ai_usage_events" in source
    assert "ai_suggestion_decisions" in source
    assert "weekly_plan_submissions" in source
    assert "private.has_role('platform_admin'" in source
    assert "Depends(require_platform_admin)" in api
    assert '"/api/v1/product-owner/usage"' in api
    assert "app.include_router(product_usage_router)" in main


def test_passive_observer_never_blocks_teacher_work() -> None:
    source = OBSERVER.read_text(encoding="utf-8")

    assert "Passive Product Owner telemetry must never interrupt teacher work" in source
    assert "originalFetch" in source
    assert '"curriculum_excel_saved"' in source
    assert '"curriculum_builder_saved"' in source
    assert '"curriculum_reused"' in source
    assert '"weekly_plan_generated"' in source
    assert '"lesson_plan_pdf_viewed"' in source
    assert '"completed_packet_viewed"' in source
    assert 'path === "/api/v1/product-usage"' not in source  # recorder bypasses observer recursion


def test_product_owner_dashboard_focuses_on_adoption_and_value_signals() -> None:
    source = DASHBOARD.read_text(encoding="utf-8")
    main = FRONTEND_MAIN.read_text(encoding="utf-8")

    assert "what teachers are actually using" in source
    assert "Pilot to date" in source
    assert "Excel pacing" in source
    assert "Build in TPP" in source
    assert "Reuse mine" in source
    assert "successful AI requests" in source
    assert "edited before use" in source
    assert "completed packets submitted" in source
    assert "Product signals" in source
    assert "not teacher-performance judgments" in source
    assert "interaction telemetry begins when this release is deployed" in source
    assert "<ProductOwnerDashboardExperience />" in main
    assert "<ProductUsageObserver />" in main
