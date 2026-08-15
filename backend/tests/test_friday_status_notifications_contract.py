from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "backend" / "app" / "friday_status_api.py"
ROUTER = ROOT / "backend" / "app" / "ai_reflection_api.py"
FRONTEND = ROOT / "frontend" / "src" / "FridayStatusExperience.tsx"
ADMIN_SUBMISSIONS = ROOT / "frontend" / "src" / "AdminSubmissionPanel.tsx"
UI_STYLES = ROOT / "frontend" / "src" / "ui-consistency.css"
MAIN = ROOT / "frontend" / "src" / "main.tsx"
STATUS_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815011000_friday_submission_status.sql"
)
DELIVERY_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815013000_scheduled_friday_notifications.sql"
)
DECISION = (
    ROOT
    / "docs"
    / "governance"
    / "FRIDAY_STATUS_NOTIFICATION_DECISION_2026-08-15.md"
)


def test_friday_status_api_is_authenticated_and_registered() -> None:
    api = API.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    assert "Depends(require_teacher)" in api
    assert "Depends(require_school_reporting_admin)" in api
    assert '"rpc/teacher_friday_submission_status"' in api
    assert '"rpc/admin_friday_submission_status"' in api
    assert "friday_status_router" in router
    assert "router.include_router(friday_status_router)" in router


def test_teacher_friday_status_ui_is_professional_operational_only() -> None:
    source = FRONTEND.read_text(encoding="utf-8")
    assert "What still needs to be submitted?" in source
    assert "This week&apos;s reflection / packet" in source
    assert "Next week&apos;s lesson plan" in source
    assert "Needs submission" in source
    assert "/api/v1/friday-status/teacher" in source
    assert "/api/v1/friday-status/admin" not in source
    assert "admin-friday-status" not in source
    forbidden = ("student_name", "student_id", "grade_result", "iep", "504")
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered


def test_administration_combines_submission_follow_up_into_weekly_report() -> None:
    source = ADMIN_SUBMISSIONS.read_text(encoding="utf-8")
    styles = UI_STYLES.read_text(encoding="utf-8")
    assert "Weekly submissions" in source
    assert "Select teachers" in source
    assert "Upcoming lesson plan" in source
    assert "Completed weekly packet" in source
    assert 'aria-label="Weekly submission status"' in source
    assert ".submission-table .submission-artifact .status" in styles
    assert "background: #e9f6ef" in styles
    assert ".submission-table td > .badge" in styles
    assert "background: #fff3d5" in styles


def test_normal_ui_uses_teacher_status_and_no_manual_email_action() -> None:
    source = MAIN.read_text(encoding="utf-8")
    assert "FridayStatusExperience" in source
    assert "AdminWeeklyDigestAction" not in source


def test_current_closeout_and_next_plan_use_immutable_submission_truth() -> None:
    source = STATUS_MIGRATION.read_text(encoding="utf-8")
    assert "public.weekly_plan_submissions" in source
    assert "public.weekly_plan_snapshots" not in source
    assert "wps.week_start = target_week_start" in source
    assert "wps.submission_kind = 'completed_packet'" in source
    assert "wps.week_start = (target_week_start + 7)::date" in source
    assert "wps.submission_kind = 'lesson_plan'" in source
    assert "calendar_days" in source
    assert "meeting_patterns" in source
    assert "schedule_exceptions" in source


def test_teacher_email_course_names_are_transient_not_persisted() -> None:
    delivery = DELIVERY_MIGRATION.read_text(encoding="utf-8")
    ledger = delivery.split(
        "create table public.scheduled_notification_deliveries",
        maxsplit=1,
    )[1].split("create index", maxsplit=1)[0]
    teacher_claim = delivery.split(
        "create or replace function public.claim_teacher_friday_reminder_candidates",
        maxsplit=1,
    )[1].split(
        "create or replace function public.claim_scheduled_admin_weekly_digest_candidates",
        maxsplit=1,
    )[0]
    assert "course_name" not in ledger
    assert "recipient_email" not in ledger
    assert "course_name" in teacher_claim
    assert "missing_current_closeout" in teacher_claim
    assert "missing_next_plan" in teacher_claim


def test_governance_locks_courtesy_window_and_deferred_activation() -> None:
    source = DECISION.read_text(encoding="utf-8").lower()
    assert "2:00 pm friday" in source
    assert "3:30 pm friday" in source
    assert "90-minute" in source
    assert "one combined courtesy reminder" in source
    assert "exact professional course/class" in source
    assert "20260815011000_friday_submission_status.sql" in source
    assert "20260815013000_scheduled_friday_notifications.sql" in source
    assert "remains deferred" in source
