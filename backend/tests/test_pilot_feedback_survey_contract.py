from pathlib import Path

from app.identity_api import PilotFeedbackWrite
from pydantic import ValidationError
import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase" / "migrations" / "20260812214500_pilot_feedback_survey.sql"
FRONTEND = ROOT / "frontend" / "src" / "PilotFeedbackExperience.tsx"
MAIN = ROOT / "frontend" / "src" / "main.tsx"
IDENTITY_API = ROOT / "backend" / "app" / "identity_api.py"


def valid_feedback() -> dict[str, object]:
    return {
        "overall_usefulness": 5,
        "planning_time_change": "much_less",
        "most_useful": "Pacing and standards alignment",
        "biggest_challenge": "Learning the first-time setup flow",
        "dislike_or_simplify": "",
        "recommended_improvement": "Keep the weekly workflow simple",
        "rollout_readiness": "ready_minor_fixes",
    }


def test_pilot_feedback_payload_has_bounded_professional_fields() -> None:
    payload = PilotFeedbackWrite.model_validate(valid_feedback())
    assert payload.overall_usefulness == 5

    too_long = valid_feedback()
    too_long["biggest_challenge"] = "x" * 1501
    with pytest.raises(ValidationError):
        PilotFeedbackWrite.model_validate(too_long)


def test_survey_uses_preferred_cycle_trigger_and_blocked_user_fallback() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "date '2026-08-21'" in source
    assert "date '2026-08-24'" in source
    assert "date '2026-08-17'" in source
    assert "submission_kind = 'completed_packet'" in source
    assert "w.week_start = date '2026-08-24'" in source
    assert "profile_roles" in source
    assert "role = 'teacher'" in source
    assert "weekly_plan_snapshots" in source
    assert "hard-coded staff list" in source
    assert "@anniston" not in source.lower()


def test_feedback_storage_is_rpc_only_and_platform_results_are_role_guarded() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    api = IDENTITY_API.read_text(encoding="utf-8")

    assert "enable row level security" in migration
    assert "revoke all on table public.pilot_feedback_responses" in migration
    assert "submit_pilot_feedback" in migration
    assert "platform_pilot_feedback_results" in migration
    assert "private.has_role('platform_admin'" in migration
    assert "Depends(require_platform_admin)" in api
    assert "Depends(require_teacher)" in api


def test_teacher_survey_is_one_time_short_and_nonblocking() -> None:
    source = FRONTEND.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")

    assert "One-time Pilot feedback" in source
    assert "about 3 minutes" in source
    assert "Remind me later" in source
    assert "What did you appreciate or find most useful?" in source
    assert "What was most challenging, confusing, or frustrating?" in source
    assert "what should we simplify or remove?" in source
    assert "what should it be?" in source
    assert "How ready is TPP for full staff rollout?" in source
    assert "Do not include student names" in source
    assert "maxLength={TEXT_LIMIT}" in source
    assert "Character limit reached" in source
    assert "<PilotFeedbackExperience />" in main


def test_product_owner_can_review_feedback_without_school_admin_exposure() -> None:
    source = FRONTEND.read_text(encoding="utf-8")

    assert "isPlatformAdmin" in source
    assert "Pilot feedback results" not in source  # heading is intentionally concise
    assert "average usefulness" in source
    assert "report less planning time" in source
    assert "ready / minor fixes" in source
    assert "teacher_name" in source
