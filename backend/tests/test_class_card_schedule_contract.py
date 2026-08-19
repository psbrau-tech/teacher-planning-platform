from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"


def test_dashboard_cards_show_class_duration_and_sort_by_start_time() -> None:
    shell = (FRONTEND / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")

    assert "function dashboardScheduleLabel(pattern: MeetingPattern)" in shell
    assert 'duration === 1 ? "" : "s"' in shell
    assert ".map((pattern) => dashboardScheduleLabel(pattern))" in shell
    assert "const dashboardAssignments = useMemo(" in shell
    assert "aTime.localeCompare(bTime) || a.course_name.localeCompare(b.course_name)" in shell
    assert "dashboardAssignments.map((assignment)" in shell


def test_course_setup_cards_remain_sorted_by_start_time() -> None:
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")

    assert "const sortedAssignments = useMemo(" in setup
    assert "aTime.localeCompare(bTime) || a.course_name.localeCompare(b.course_name)" in setup
    assert "sortedAssignments.map((assignment)" in setup
