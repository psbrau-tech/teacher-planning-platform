from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
SHELL = FRONTEND / "TeacherPlanningShell.tsx"
COURSE_SETUP = FRONTEND / "CourseSetupPanel.tsx"
CURRICULUM_ROWS = FRONTEND / "curriculumRows.ts"
WEEKLY_CONTEXT = FRONTEND / "WeeklyPlanningContext.tsx"
PLANNING = FRONTEND / "AiPlanningPanel.tsx"
HELP = FRONTEND / "HelpPage.tsx"
MAIN = FRONTEND / "main.tsx"


def test_course_setup_and_planning_components_exist() -> None:
    source = SHELL.read_text(encoding="utf-8")
    assert 'from "./CourseSetupPanel"' in source
    assert 'from "./AiPlanningPanel"' in source
    assert 'from "./PlanningPdfFieldsPanel"' in source
    assert 'from "./StandardsPanel"' in source
    assert 'from "./AiReflectionPanel"' in source


def test_course_setup_keeps_schedule_and_curriculum_separate() -> None:
    source = COURSE_SETUP.read_text(encoding="utf-8")
    assert "Class & Schedule" in source
    assert "Curriculum & Pacing" in source
    assert "Save class & continue" in source
    assert "Save Curriculum & Pacing & Continue" in source


def test_planning_requires_teacher_review_before_saved_work() -> None:
    source = PLANNING.read_text(encoding="utf-8")
    assert "Suggested text — not saved" in source
    assert "Use suggestion" in source
    assert "Use edited text" in source
    assert "Skip suggestion" in source


def test_planning_pdf_fields_include_required_district_fields() -> None:
    source = (FRONTEND / "PlanningPdfFieldsPanel.tsx").read_text(encoding="utf-8")
    for label in (
        "Literacy Standards",
        "ACT Preparation",
        "Performance-Level Descriptors / Proficiency Scale",
        "Likely Misconceptions",
        "Formative Assessments",
        "Summative Assessments",
        "Performance Task / Authentic Application",
    ):
        assert label in source


def test_standards_panel_is_grouped_and_saves_weekly_selection() -> None:
    source = (FRONTEND / "StandardsPanel.tsx").read_text(encoding="utf-8")
    assert '<details className="standard-group"' in source
    assert 'new CustomEvent("tpp:standards-saved"' in source


def test_course_setup_is_progressive_and_keeps_curriculum_out_of_step_one() -> None:
    shell = SHELL.read_text(encoding="utf-8")
    setup = COURSE_SETUP.read_text(encoding="utf-8")
    parser = CURRICULUM_ROWS.read_text(encoding="utf-8")

    assert 'from "./CourseSetupPanel"' in shell
    assert "<CourseSetupPanel" in shell
    assert 'from "./curriculumRows"' in setup
    assert "parseCurriculumRows" in setup
    assert 'from "./StandardsCourseMappingPanel"' in setup
    assert "<StandardsCourseMappingPanel" in setup
    assert "Step 1" in setup and "Class & Schedule" in setup
    assert "Step 2" in setup and "Curriculum & Pacing" in setup
    assert "Step 3" in setup and "Authoritative Standards" in setup
    assert "Step 4 · Ready" in setup
    assert "Save class & continue" in setup
    assert "Upload Excel" in setup
    assert "Build in TPP" in setup
    assert "Reuse mine" in setup
    assert "Nothing is saved" in setup
    assert "Save Curriculum & Pacing & Continue" in setup
    assert "My Curriculum & Pacing" in setup
    assert "Remove from my list" in setup
    assert "Add another class" in setup
    assert "Grade(s)" in setup
    assert "Edit class" in setup
    assert "submitted packets, and reusable curricula will be preserved" in setup
    # Class creation no longer exposes or silently creates a curriculum selector/placeholder.
    save_class = setup.split("async function saveClass", 1)[1].split(
        "async function removeClass", 1
    )[0]
    assert "createPlaceholderCurriculum" not in setup
    assert 'form.get("curriculum_id")' not in save_class
    assert "curriculum_id: editing?.curriculum_id ?? null" in save_class
    assert "estimated_minutes: number | null" in parser
    assert "if (!value.trim()) return null" in parser
    assert "earlierSixColumn" in parser
    assert "legacyMinutes" in parser
    assert "parts.length >= 6" in parser


def test_weekly_plan_uses_live_standards_without_repeating_primary_mapping() -> None:
    shell = SHELL.read_text(encoding="utf-8")
    schedule = WEEKLY_CONTEXT.read_text(encoding="utf-8")

    assert 'from "./StandardsPanel"' in shell
    assert "<StandardsPanel" in shell
    assert "weeklyLessons={plan}" in shell
    assert "standardsMappingVersion" in shell
    assert "StandardsCourseMappingPanel" not in shell

    assert "StandardsCourseMappingPanel" not in schedule
    assert "CanonicalStandardsPanel" not in schedule


def test_weekly_plan_and_friday_closeout_are_progressive() -> None:
    shell = SHELL.read_text(encoding="utf-8")

    for label in (
        "Build Week",
        "Standards",
        "Planning Assist",
        "Review & Save",
        "Review PDF",
        "Submit",
    ):
        assert label in shell
    for label in ("Validate", "Reflect & Submit", "Review Packet", "Continue"):
        assert label in shell
    assert "Confirm this week's curriculum & continue" in shell
    assert "Review completed weekly packet" in shell
    assert "View completed packet" in shell
    assert "Download PDF" in shell
    assert "Print" in shell
    assert "/api/v1/teacher-submissions/" in shell
    assert "Continue to next week" in shell


def test_help_is_discoverable_and_uses_authenticated_roles() -> None:
    shell = SHELL.read_text(encoding="utf-8")
    help_source = HELP.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")

    assert 'view === "help"' in shell
    assert 'setView("help")' in shell
    assert "<HelpPage roles={identity.roles}" in shell
    assert "<TeacherPlanningShell />" in main
    assert 'roles={["teacher", "school_admin"]}' not in main
    assert "Class & Schedule" in help_source
    assert "Upload Excel" in help_source
    assert "Save Curriculum & Pacing & Continue" in help_source
    assert "Review the Completed Weekly Packet" in help_source
    assert "Monday" in help_source


def test_ai_planning_remains_teacher_reviewed_and_recoverable() -> None:
    planning = PLANNING.read_text(encoding="utf-8")

    assert "Suggested text — not saved" in planning
    assert "Use suggestion" in planning
    assert "Use edited text" in planning
    assert "Skip suggestion" in planning
    assert "Generate another suggestion" in planning
    assert "Use all remaining suggestions" in planning
    assert "fieldToRegenerate?: PlanningFieldKey" in planning
    assert "BASE_FIELD_SET.has(fieldToRegenerate)" in planning
