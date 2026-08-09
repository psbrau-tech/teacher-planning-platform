from pathlib import Path


def test_weekly_plan_mounts_schedule_exception_controls() -> None:
    root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    shell_source = (root / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")
    panel_source = (root / "ScheduleExceptionPanel.tsx").read_text(encoding="utf-8")

    assert 'import { ScheduleExceptionPanel } from "./ScheduleExceptionPanel";' in shell_source
    assert "<ScheduleExceptionPanel" in shell_source
    assert "assignmentId={selectedAssignmentId}" in shell_source
    assert "weekStart={weekStart}" in shell_source
    assert "setPlan([]);" in shell_source
    assert "setValidations({});" in shell_source

    assert "/api/v1/schedule-exceptions?assignment_id=" in panel_source
    assert "Day unavailable" in panel_source
    assert "Reduced instructional minutes" in panel_source
    assert "Save exception" in panel_source
    assert "Remove exception" in panel_source
    assert "Regenerate the week" in panel_source

    # Schedule adjustment remains schedule-only; standards render once in the shell.
    assert "CanonicalStandardsPanel" not in panel_source
    assert "StandardsCourseMappingPanel" not in panel_source
