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


def test_owner_baseline_uses_five_point_distribution_chart() -> None:
    overview = (FRONTEND / "AdministrationOverview.tsx").read_text(encoding="utf-8")
    chart = (FRONTEND / "BaselineBarChart.tsx").read_text(encoding="utf-8")
    assert "averageReflectionReview" in overview
    assert "averagePlcUse" in overview
    assert "<BaselineBarChart responses={summary.responses}" in overview
    assert "Baseline response distribution" in chart
    assert "Grouped vertical bar chart" in chart
    assert "countScores" in chart
    assert "never: 1" in chart
    assert "very_often: 5" in chart
