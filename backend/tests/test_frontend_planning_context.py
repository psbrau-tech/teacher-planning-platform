from pathlib import Path


def test_frontend_clears_stale_planning_context_on_course_and_week_changes() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "TeacherPlanningShell.tsx"
    ).read_text(encoding="utf-8")

    assert "function clearPlanningContext(" in source
    assert "selectPlanningAssignment(event.target.value)" in source
    assert "selectPlanningWeek(event.target.value)" in source

    # Workflow entry points must not reuse whichever week the teacher happened to view last.
    assert "function openFridayCloseout(" in source
    assert "const currentWeek = mondayFor();" in source
    assert "clearPlanningContext(assignment, currentWeek);" in source
    assert 'setView("validation");' in source
    assert "function openPlanningWeek(" in source
    assert "clearPlanningContext(assignment, targetWeek);" in source
    assert "mondayFor()" in source
    assert "addDays(mondayFor(), 7)" in source
    assert "Friday validation" in source
    assert "Course Setup" in source

    # Friday optimistic concurrency must carry the loaded revision through browser state.
    assert "const [validationRevision, setValidationRevision]" in source
    assert "setValidationRevision(saved.revision);" in source
    assert "expected_revision: validationRevision" in source

    # Friday closeout persists teacher-owned reflection through its dedicated endpoint.
    assert "async function saveCloseoutDraft()" in source
    closeout = source.split("async function saveCloseoutDraft()", 1)[1].split(
        "async function submitDraft", 1
    )[0]
    assert "/api/v1/weekly-drafts/friday-closeout" in closeout
    assert "literacy_standards" not in closeout
    assert "act_preparation" not in closeout

    assert 'onChange={(event) => setSelectedAssignmentId(event.target.value)}' not in source
    assert 'onChange={(event) => setWeekStart(event.target.value)}' not in source
