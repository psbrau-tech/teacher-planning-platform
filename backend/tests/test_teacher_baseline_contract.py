from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase" / "migrations" / "20260813050000_teacher_baseline_survey.sql"
API = ROOT / "backend" / "app" / "baseline_api.py"
MAIN_API = ROOT / "backend" / "app" / "main.py"
SURVEY = ROOT / "frontend" / "src" / "BaselineSurveyExperience.tsx"
ADMINISTRATION = ROOT / "frontend" / "src" / "AdministrationOverview.tsx"
FRONTEND_MAIN = ROOT / "frontend" / "src" / "main.tsx"
PILOT_CSS = ROOT / "frontend" / "src" / "pilot-feedback.css"


def test_baseline_storage_is_governed_and_pre_tpp_only() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "create table public.teacher_baseline_responses" in source
    assert "teacher-baseline-2026-08" in source
    assert "planning_time_before" in source
    assert "plan_usefulness_before" in source
    assert "submission_burden_before" in source
    assert "reflection_review_frequency_before" in source
    assert "plc_use_frequency_before" in source
    assert "alter table public.teacher_baseline_responses enable row level security" in source
    assert "revoke all on table public.teacher_baseline_responses" in source
    assert "No student-specific information permitted" in source
    assert "Platform Owner results intentionally omit teacher identity" in source
    assert "teacher_name" not in source
    assert "private.has_role('platform_admin'" in source


def test_baseline_api_is_teacher_write_and_owner_read() -> None:
    api = API.read_text(encoding="utf-8")
    main = MAIN_API.read_text(encoding="utf-8")
    assert 'router = APIRouter(prefix="/api/v1/baseline"' in api
    assert "Depends(require_teacher)" in api
    assert "Depends(require_platform_admin)" in api
    assert "teacher_baseline_status" in api
    assert "submit_teacher_baseline" in api
    assert "platform_teacher_baseline_results" in api
    assert "app.include_router(baseline_router)" in main


def test_teacher_baseline_explicitly_anchors_answers_before_tpp() -> None:
    source = SURVEY.read_text(encoding="utf-8")
    main = FRONTEND_MAIN.read_text(encoding="utf-8")
    assert "Think about your planning process before TPP" in source
    assert "normal experience before you began using TPP" in source
    assert "Even if you have already used TPP this week" in source
    assert source.count("Before TPP") >= 6
    assert "60–90 seconds" in source
    assert "Continue for now" in source
    assert "Do not include student names" in source
    assert "<BaselineSurveyExperience />" in main


def test_owner_reporting_is_consolidated_away_from_admin_and_floating_launchers() -> None:
    administration = ADMINISTRATION.read_text(encoding="utf-8")
    pilot_css = PILOT_CSS.read_text(encoding="utf-8")
    assert 'aria-selected={activeTab === "owner"}' in administration
    assert 'onClick={() => setActiveTab("owner")}' in administration
    assert ">Owner</button>" in administration
    assert "Product and Pilot intelligence" in administration
    assert "<ProductOwnerDashboardExperience />" in administration
    assert "<PilotFeedbackResultsPanel" in administration
    assert "What planning looked like before TPP" in administration
    assert "<StandardsAdministrationPanel" in administration
    assert "AI cost reporting" in administration
    assert "Platform Owner results intentionally omit teacher identity" not in administration
    assert ".pilot-feedback-owner-button" in pilot_css
    assert "display: none" in pilot_css
