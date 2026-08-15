from pathlib import Path

from app.daily_assessment_analytics import (
    analyze_daily_assessment_sources,
    classify_daily_assessment,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815001500_daily_formative_assessment_analytics.sql"
)
API = ROOT / "backend" / "app" / "daily_assessment_api.py"
EXPERIENCE = ROOT / "frontend" / "src" / "DailyAssessmentAnalyticsExperience.tsx"
MAIN = ROOT / "frontend" / "src" / "main.tsx"


def test_exit_slips_and_common_daily_checks_are_recognized() -> None:
    assert classify_daily_assessment("Exit slip: one misconception", "") == ["exit_ticket"]
    assert classify_daily_assessment("Cold-call questioning", "Mini-whiteboard responses") == [
        "whiteboard_response",
        "questioning_discussion",
    ]
    assert classify_daily_assessment("", "Quizizz retrieval check") == [
        "digital_check",
        "retrieval_warmup",
    ]


def test_unrecognized_nonblank_assessment_is_preserved_as_other() -> None:
    assert classify_daily_assessment("Teacher-created diagnostic routine", "") == [
        "other_formative"
    ]
    assert classify_daily_assessment("", "") == []


def test_source_analysis_counts_days_not_raw_text_fragments() -> None:
    rows = [
        {
            "source_ref": 1,
            "anonymous_teacher_ref": 1,
            "week_start": "2026-08-10",
            "daily_assessment_data": {
                "cfu_mon": "Exit ticket",
                "esl_mon": "Exit slip response",
                "cfu_tue": "Cold-call questioning",
                "esl_tue": "",
                "cfu_wed": "",
                "esl_wed": "",
                "cfu_thu": "",
                "esl_thu": "Quizizz",
                "cfu_fri": "",
                "esl_fri": "Teacher-created diagnostic routine",
            },
        },
        {
            "source_ref": 2,
            "anonymous_teacher_ref": 2,
            "week_start": "2026-08-10",
            "daily_assessment_data": {
                "cfu_mon": "",
                "esl_mon": "",
                "cfu_tue": "Thumbs up/down",
                "esl_tue": "",
                "cfu_wed": "",
                "esl_wed": "",
                "cfu_thu": "",
                "esl_thu": "",
                "cfu_fri": "Exit slip",
                "esl_fri": "",
            },
        },
    ]
    analysis = analyze_daily_assessment_sources(rows)

    assert analysis["submitted_course_weeks"] == 2
    assert analysis["distinct_teachers"] == 2
    assert analysis["daily_assessment_entries"] == 6
    assert analysis["type_counts"]["exit_ticket"] == 2
    assert analysis["type_counts"]["other_formative"] == 1
    assert analysis["weekday_counts"]["Monday"] == 1
    assert analysis["weekday_counts"]["Friday"] == 2


def test_database_source_uses_only_immutable_submitted_lesson_plans() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "public.weekly_plan_submissions" in source
    assert "wps.submission_kind = 'lesson_plan'" in source
    assert "public.weekly_plan_snapshots" not in source
    assert "distinct on (wps.teaching_assignment_id, wps.week_start)" in source
    assert "private.can_report_school" in source
    assert "dense_rank() over (order by latest.teacher_id)" in source
    assert "anonymous_teacher_ref" in source
    assert "teacher_name" not in source
    assert "source_data ->> 'reflection'" not in source
    assert "wps.submission_kind = 'completed_packet'" not in source


def test_database_source_returns_only_daily_cfu_and_evidence_fields() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for prefix in ("cfu", "esl"):
        for suffix in ("mon", "tue", "wed", "thu", "fri"):
            assert f"'{prefix}_{suffix}'" in source
    assert "source_data ->> 'formative'" not in source
    assert "source_data ->> 'summative'" not in source
    assert "course_name" not in source


def test_api_returns_aggregate_counts_without_raw_plan_text() -> None:
    source = API.read_text(encoding="utf-8")
    assert 'source_scope: str = "immutable-submitted-lesson-plans"' in source
    assert 'classification_method: str = "deterministic-keyword-v1"' in source
    assert 'interpretation: str = "planned-formative-assessment-signals-only"' in source
    assert 'evaluation: str = "none"' in source
    assert "daily_assessment_data" not in source
    assert "teacher_name" not in source
    assert "course_name" not in source


def test_frontend_frames_assessment_mix_as_planning_not_performance() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8").lower()
    assert "planned daily formative-assessment mix" in source
    assert "exit tickets" in source
    assert "not a teacher-performance measure" in source
    assert "not evidence that an assessment was actually administered" in source
    assert "no lesson-plan text is sent to ai" in source
    assert "other / not yet classified" in source


def test_daily_assessment_analytics_is_mounted() -> None:
    source = MAIN.read_text(encoding="utf-8")
    assert 'import { DailyAssessmentAnalyticsExperience }' in source
    assert "<DailyAssessmentAnalyticsExperience />" in source
