from pathlib import Path


def test_weekly_plan_mounts_schedule_exception_controls() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    frontend_root = repository_root / "frontend" / "src"
    shell_source = (frontend_root / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")
    panel_source = (frontend_root / "ScheduleExceptionPanel.tsx").read_text(encoding="utf-8")
    move_api_source = (
        repository_root / "backend" / "app" / "planned_lesson_api.py"
    ).read_text(encoding="utf-8")

    assert "ScheduleExceptionPanel" in shell_source
    assert 'from "./ScheduleExceptionPanel";' in shell_source
    assert "<ScheduleExceptionPanel" in shell_source
    assert "assignmentId={selectedAssignmentId}" in shell_source
    assert "weekStart={weekStart}" in shell_source
    assert "onExceptionsChanged={setScheduleExceptions}" in shell_source
    assert "const unavailable = new Set(" in shell_source
    assert ".filter((exception) => !exception.is_available)" in shell_source
    assert "setPlan([]);" in shell_source
    assert "setWeekCurriculumConfirmed(false);" in shell_source
    assert "setValidations({});" in shell_source

    assert "/api/v1/schedule-exceptions?assignment_id=" in panel_source
    assert "onExceptionsChanged" in panel_source
    assert "Day unavailable" in panel_source
    assert "Reduced instructional minutes" in panel_source
    assert "Save exception" in panel_source
    assert "Remove exception" in panel_source
    assert "Regenerate the week" in panel_source

    # The API independently rejects a move to a saved unavailable exception date.
    assert '"schedule_exceptions"' in move_api_source
    assert 'exception_rows[0].get("is_available") is False' in move_api_source
    assert "That date is unavailable for this class" in move_api_source

    # Schedule adjustment remains schedule-only; standards render once in the shell.
    assert "CanonicalStandardsPanel" not in panel_source
    assert "StandardsCourseMappingPanel" not in panel_source
