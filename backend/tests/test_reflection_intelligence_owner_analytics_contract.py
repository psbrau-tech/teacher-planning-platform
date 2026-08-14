from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIENCE = ROOT / "frontend" / "src" / "OwnerReflectionIntelligenceAnalytics.tsx"
MAIN = ROOT / "frontend" / "src" / "main.tsx"


def test_owner_reflection_intelligence_analytics_is_mounted() -> None:
    source = MAIN.read_text(encoding="utf-8")
    assert 'import { OwnerReflectionIntelligenceAnalytics }' in source
    assert "<OwnerReflectionIntelligenceAnalytics />" in source


def test_owner_analytics_reads_only_content_free_usage_endpoints() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")

    assert "/api/v1/reflection-intelligence/usage" in source
    assert "/api/v1/notifications/usage" in source
    assert "teacher_recaps_generated" in source
    assert "school_plc_briefs_generated" in source
    assert "plc_handouts_viewed" in source
    assert "admin_weekly_digests_sent" in source

    forbidden = (
        "reflection_text",
        "teacher_name",
        "student_name",
        "teacher_score",
        "performance_score",
    )
    for phrase in forbidden:
        assert phrase not in source


def test_owner_analytics_explicitly_rejects_performance_interpretation() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8").lower()

    assert "product-adoption signals" in source
    assert "not teacher performance" in source
    assert "not teacher performance," in source
    assert "quality, effort, or productivity measures" in source
    assert "do not use them to rank staff" in source
    assert "contain no reflection text or student data" in source


def test_owner_analytics_supports_bounded_reporting_periods() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")

    assert 'type PeriodKind = "current_week" | "last_4_weeks" | "release_to_date" | "custom"' in source
    assert 'start: "2026-08-14"' in source
    assert "period_start" in source
    assert "period_end" in source
