from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"


def test_selected_teacher_usage_filter_closes_on_outside_click() -> None:
    source = (FRONTEND / "AdminSelectedTeacherUsageReport.tsx").read_text(encoding="utf-8")
    assert "useRef" in source
    assert "teacherFilterRef" in source
    assert "closeTeacherFilterOnOutsidePointer" in source
    assert "document.addEventListener(\"pointerdown\"" in source


def test_weekly_submission_report_waits_for_teacher_selection() -> None:
    source = (FRONTEND / "AdminSubmissionPanel.tsx").read_text(encoding="utf-8")
    assert "Select teachers" in source
    assert "selectedTeacherIds.size === 0" in source
    assert "Select one or more teachers to build the weekly submission report." in source


def test_owner_baseline_includes_accessible_bar_chart() -> None:
    overview = (FRONTEND / "AdministrationOverview.tsx").read_text(encoding="utf-8")
    chart = (FRONTEND / "BaselineBarChart.tsx").read_text(encoding="utf-8")
    assert "<BaselineBarChart" in overview
    assert "Baseline at a glance" in chart
    assert 'aria-label="Pre-TPP baseline bar chart"' in chart
    assert "averageUsefulness" in overview
    assert "averageBurden" in overview
    assert "rarelyReviewReflection" in overview
    assert "rarelyUseInPlc" in overview
