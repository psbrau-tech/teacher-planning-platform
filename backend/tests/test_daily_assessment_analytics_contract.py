from pathlib import Path

from app.daily_assessment_analytics import (
    analyze_daily_assessment_sources,
    analyze_daily_assessment_weekly_trends,
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
DECISION = (
    ROOT
    / "docs"
    / "governance"
    / "DAILY_FORMATIVE_ASSESSMENT_ANALYTICS_DECISION_2026-08-14.md"
)


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


def test_weekly_trends_reuse_same_classifier_and_preserve_weekly_coverage() -> None:
    rows = [
        {
            "anonymous_teacher_ref": 1,
            "week_start": "2026-08-03",
            "daily_assessment_data": {
                "cfu_mon": "Exit ticket",
                "cfu_tue": "Quick write",
            },
        },
        {
            "anonymous_teacher_ref": 2,
            "week_start": "2026-08-03",
            "daily_assessment_data": {"cfu_fri": "Exit slip"},
        },
        {
            "anonymous_teacher_ref": 1,
            "week_start": "2026-08-10",
            "daily_assessment_data": {"cfu_wed": "Cold-call questioning"},
        },
        {
            "anonymous_teacher_ref": 99,
            "week_start": "not-a-date",
            "daily_assessment_data": {"cfu_mon": "Exit ticket"},
        },
    ]

    trends = analyze_daily_assessment_weekly_trends(rows)

    assert [item["week_start"].isoformat() for item in trends] == [
        "2026-08-03",
        "2026-08-10",
    ]
    assert trends[0]["submitted_course_weeks"] == 2
    assert trends[0]["distinct_teachers"] == 2
    assert trends[0]["daily_assessment_entries"] == 3
    assert trends[0]["type_counts"]["exit_ticket"] == 2
    assert trends[0]["type_counts"]["quick_write"] == 1
    assert trends[1]["submitted_course_weeks"] == 1
    assert trends[1]["distinct_teachers"] == 1
    assert trends[1]["type_counts"]["questioning_discussion"] == 1


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


def test_api_returns_aggregate_counts_and_weekly_trends_without_raw_plan_text() -> None:
    source = API.read_text(encoding="utf-8")
    assert 'source_scope: str = "immutable-submitted-lesson-plans"' in source
    assert 'classification_method: str = "deterministic-keyword-v1"' in source
    assert 'interpretation: str = "planned-formative-assessment-signals-only"' in source
    assert 'evaluation: str = "none"' in source
    assert "weekly_trends: list[WeeklyAssessmentTrendRead]" in source
    assert "analyze_daily_assessment_weekly_trends(source_rows)" in source
    assert "daily_assessment_data" not in source
    assert "teacher_name" not in source
    assert "course_name" not in source


def test_frontend_frames_assessment_mix_and_trends_as_planning_not_performance() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8").lower()
    assert "planned daily formative-assessment mix" in source
    assert "week-over-week planned assessment trend" in source
    assert "exit tickets / slips" in source
    assert "submitted course-week and anonymous teacher coverage" in source
    assert "does not normalize these counts into teacher comparisons" in source
    assert "not a teacher-performance measure" in source
    assert "assessment was actually administered" in source
    assert "students mastered the content" in source
    assert "no lesson-plan text is sent to ai" in source
    assert "other / not yet classified" in source


def test_weekly_trend_governance_rejects_compliance_rate_interpretation() -> None:
    source = DECISION.read_text(encoding="utf-8").lower()

    assert "raw school-level planning counts" in source
    assert "does not assume every course meets five days per week" in source
    assert "exit tickets/slips remain visible" in source
    assert "compliance rate" in source
    assert "no new assessment-content retention store" in source


def test_daily_assessment_analytics_is_mounted() -> None:
    source = MAIN.read_text(encoding="utf-8")
    assert 'import { DailyAssessmentAnalyticsExperience }' in source
    assert "<DailyAssessmentAnalyticsExperience />" in source
