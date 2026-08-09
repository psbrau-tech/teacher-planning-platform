from pathlib import Path


def test_frontend_clears_stale_planning_context_on_course_and_week_changes() -> None:
    source = (
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "main.tsx"
    ).read_text(encoding="utf-8")

    assert "function clearPlanningContext(" in source
    assert "clearPlanningContext(created, weekStart);" in source
    assert source.count("selectPlanningAssignment(event.target.value)") == 2
    assert source.count("selectPlanningWeek(event.target.value)") == 2

    # Workflow entry points must not reuse whichever week the teacher happened to view last.
    assert "function openFridayCloseout(" in source
    assert "const currentWeek = mondayFor();" in source
    assert "clearPlanningContext(assignment, currentWeek);" in source
    assert 'setView("validation");' in source
    assert "function openPlanningWeek(" in source
    assert "clearPlanningContext(assignment, targetWeek);" in source
    assert 'onClick={() => openPlanningWeek(mondayFor())}>Open weekly plan' in source
    assert (
        'onClick={() => openPlanningWeek(addDays(mondayFor(), 7))}>'
        "Plan next week early"
        in source
    )
    assert "Friday validation → required teacher reflection" in source
    assert "Complete Friday validation" in source
    assert "Course Setup" in source
    assert "Create your class schedule" in source

    # Friday optimistic concurrency must carry the loaded revision through browser state.
    assert "const [validationRevision, setValidationRevision]" in source
    assert "setValidationRevision(saved.revision);" in source
    assert "expected_revision: validationRevision" in source

    # Friday closeout persists the teacher-owned reflection without reusing weekly-plan
    # Literacy Standards / ACT Preparation validation.
    assert "async function saveCloseoutDraft()" in source
    closeout = source.split("async function saveCloseoutDraft()", 1)[1].split(
        "async function submitDraft", 1
    )[0]
    assert "literacy_standards" not in closeout
    assert "act_preparation" not in closeout
    assert "const saved = await saveCloseoutDraft();" in source
    assert 'onClick={() => void saveCloseoutDraft()}>Save Friday closeout' in source

    assert 'onChange={(event) => setSelectedAssignmentId(event.target.value)}' not in source
    assert 'onChange={(event) => setWeekStart(event.target.value)}' not in source
    assert 'setSelectedAssignmentId(assignment.id); setView("plan");' not in source
