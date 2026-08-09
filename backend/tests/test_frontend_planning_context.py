from pathlib import Path


def test_frontend_clears_stale_planning_context_on_course_and_week_changes() -> None:
    source = (
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "main.tsx"
    ).read_text(encoding="utf-8")

    assert "function clearPlanningContext(" in source
    assert "clearPlanningContext(created, weekStart);" in source
    assert source.count("selectPlanningAssignment(event.target.value)") == 2
    assert source.count("selectPlanningWeek(event.target.value)") == 2
    assert 'selectPlanningAssignment(assignment.id); setView("validation");' in source
    assert "Plan next week early" in source
    assert "Friday validation → required teacher reflection" in source

    assert 'onChange={(event) => setSelectedAssignmentId(event.target.value)}' not in source
    assert 'onChange={(event) => setWeekStart(event.target.value)}' not in source
    assert 'setSelectedAssignmentId(assignment.id); setView("plan");' not in source
