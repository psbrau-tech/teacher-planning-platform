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
    source = (FRONTEND / "AdministrationOverview.tsx").read_text(encoding="utf-8")
    assert "Baseline at a glance" in source
    assert 'aria-label="Pre-TPP baseline bar chart"' in source
    assert "averageUsefulness" in source
    assert "averageBurden" in source
    assert "rarelyReviewReflection" in source
    assert "rarelyUseInPlc" in source
