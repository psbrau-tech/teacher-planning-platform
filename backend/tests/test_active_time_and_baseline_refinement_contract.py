from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_RANGE = (
    ROOT / "supabase" / "migrations" / "20260813050500_teacher_baseline_time_ranges.sql"
)
ACTIVE_TIME = (
    ROOT / "supabase" / "migrations" / "20260813051000_product_active_time_telemetry.sql"
)
BASELINE_API = ROOT / "backend" / "app" / "baseline_api.py"
PRODUCT_API = ROOT / "backend" / "app" / "product_usage_api.py"
SURVEY = ROOT / "frontend" / "src" / "BaselineSurveyExperience.tsx"
OBSERVER = ROOT / "frontend" / "src" / "ProductUsageObserver.tsx"
OWNER = ROOT / "frontend" / "src" / "ProductOwnerDashboardExperience.tsx"
BREAKOUT = ROOT / "frontend" / "src" / "OwnerActiveTimeBreakout.tsx"
ADMINISTRATION = ROOT / "frontend" / "src" / "AdministrationOverview.tsx"
EVENT_KEYS = ROOT / "frontend" / "src" / "productUsage.ts"
MAIN = ROOT / "frontend" / "src" / "main.tsx"


def test_baseline_splits_the_one_to_two_hour_range_before_deployment() -> None:
    migration = BASELINE_RANGE.read_text(encoding="utf-8")
    api = BASELINE_API.read_text(encoding="utf-8")
    survey = SURVEY.read_text(encoding="utf-8")

    for key in ("61_90", "91_120"):
        assert key in migration
        assert key in api
        assert key in survey

    assert 'value="61_90">61–90 minutes' in survey
    assert 'value="91_120">91–120 minutes' in survey
    assert '"61_120"' not in api
    assert 'value="61_120"' not in survey


def test_active_time_is_bounded_content_free_and_platform_owner_only() -> None:
    migration = ACTIVE_TIME.read_text(encoding="utf-8")
    api = PRODUCT_API.read_text(encoding="utf-8")

    assert "active_course_setup_30s" in migration
    assert "active_weekly_planning_30s" in migration
    assert "active_reflection_30s" in migration
    assert "active_friday_closeout_30s" in migration
    assert "reflection_total_seconds" in migration
    assert "median_reflection_seconds_per_teacher_week" in migration
    assert "median_onboarding_reflection_seconds" in migration
    assert "median_steady_state_reflection_seconds" in migration
    assert "platform_product_active_time_summary" in migration
    assert "interval '14 days'" in migration
    assert "private.has_role('platform_admin'" in migration
    assert "No planning/reflection content is stored" in migration
    assert '"/api/v1/product-owner/active-time"' in api
    assert "reflection_total_seconds: int = 0" in api
    assert "median_reflection_seconds_per_teacher_week: int = 0" in api
    assert "Depends(require_platform_admin)" in api


def test_browser_active_time_stops_for_hidden_or_idle_tabs_and_avoids_double_tabs() -> None:
    observer = OBSERVER.read_text(encoding="utf-8")
    keys = EVENT_KEYS.read_text(encoding="utf-8")

    assert "ACTIVE_HEARTBEAT_MS = 30_000" in observer
    assert "ACTIVE_IDLE_CUTOFF_MS = 60_000" in observer
    assert 'document.visibilityState !== "visible"' in observer
    assert "ACTIVE_LEASE_KEY" in observer
    assert "ownsActiveLease" in observer
    assert 'querySelector(".baseline-backdrop, .pilot-feedback-backdrop")' in observer
    assert 'label === "Course Setup"' in observer
    assert 'label === "Weekly plan"' in observer
    assert 'label === "Friday validation"' in observer
    assert 'querySelector(".ai-reflection-panel")' in observer
    assert 'return "active_reflection_30s"' in observer
    assert "active_course_setup_30s" in keys
    assert "active_weekly_planning_30s" in keys
    assert "active_reflection_30s" in keys
    assert "active_friday_closeout_30s" in keys


def test_active_time_is_presented_as_product_measurement_not_teacher_evaluation() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    breakout = BREAKOUT.read_text(encoding="utf-8")
    administration = ADMINISTRATION.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")

    assert "Active TPP interaction time" in owner
    assert "not login duration and not total teacher planning time" in owner
    assert "14 days of measured use" in owner
    assert "exposed to school or district administrators" in owner
    assert "onboarding weekly-plan median" in owner
    assert "steady-state weekly-plan median" in owner
    assert "/api/v1/product-owner/active-time" in owner

    assert "Planning vs reflection" in breakout
    assert "Weekly Planning includes the planning workflow and AI-assisted" in breakout
    assert "Teacher Reflection measures the required 12-prompt reflection step separately" in breakout
    assert "Friday Closeout excludes reflection" in breakout
    assert "median Teacher Reflection active minutes" in breakout
    assert "onboarding reflection median" in breakout
    assert "steady-state reflection median" in breakout
    assert "School and district administrators do not receive" in breakout
    assert 'document.querySelector(".owner-tab")' in breakout
    assert "<OwnerActiveTimeBreakout />" in main

    # School/district administration must not load or display Product Owner duration metrics.
    assert "/api/v1/product-owner/active-time" not in administration
    assert "Active TPP interaction time" not in administration
    assert "Teacher Reflection active minutes" not in administration
