from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
SHELL = FRONTEND / "TeacherPlanningShell.tsx"
COURSE_SETUP = FRONTEND / "CourseSetupPanel.tsx"
CURRICULUM_ROWS = FRONTEND / "curriculumRows.ts"
MAPPING = FRONTEND / "StandardsCourseMappingPanel.tsx"
CANONICAL_STANDARDS = FRONTEND / "CanonicalStandardsPanel.tsx"
LIVE_STANDARDS = FRONTEND / "StandardsPanel.tsx"
PLANNING = FRONTEND / "AiPlanningPanel.tsx"
REFLECTION = FRONTEND / "AiReflectionPanel.tsx"
WEEKLY_CONTEXT = FRONTEND / "ScheduleExceptionPanel.tsx"
STANDARDS_ADMIN = FRONTEND / "StandardsAdministrationPanel.tsx"
ACT_ADMIN = FRONTEND / "ActReferenceAdministrationPanel.tsx"
HELP = FRONTEND / "HelpPage.tsx"
MAIN = FRONTEND / "main.tsx"


def test_teacher_mapping_uses_two_step_catalog_and_explicit_correction_warning() -> None:
    source = MAPPING.read_text(encoding="utf-8")

    assert "Subject / Career Cluster" in source
    assert "Grade / Course" in source
    assert "/api/v1/standards/catalog/categories" in source
    assert "/courses" in source
    assert "Change standards mapping?" in source
    assert "confirm_existing_plans" in source
    assert "I understand that this changes the standards available" in source
    assert "validated weeks will retain the exact standards" in source.lower()
    assert "open, unvalidated weeks will be cleared" in source.lower()


def test_mapping_and_standards_requests_use_teacher_bearer_token() -> None:
    mapping = MAPPING.read_text(encoding="utf-8")
    canonical = CANONICAL_STANDARDS.read_text(encoding="utf-8")
    live = LIVE_STANDARDS.read_text(encoding="utf-8")

    assert 'Authorization: `Bearer ${accessToken}`' in mapping
    assert 'Authorization: `Bearer ${accessToken}`' in canonical
    assert 'Authorization: `Bearer ${accessToken}`' in live
    assert "catalog_course_id" in mapping
    assert "standard_entry_ids" in canonical
    assert "standard_entry_ids" in live


def test_weekly_standard_selector_shows_canonical_course_and_exact_source_provenance() -> None:
    source = CANONICAL_STANDARDS.read_text(encoding="utf-8")

    assert "catalog_category" in source
    assert "catalog_course" in source
    assert "sources: StandardSource[]" in source
    assert "Supplemental authority" in source
    assert "View authoritative source" in source
    assert "exact standard entry" in source
    assert "AI cannot rewrite authoritative wording" in source
    assert "Search by code, wording, strand, or source" in source


def test_live_weekly_selector_prioritizes_scheduled_lesson_relevance() -> None:
    source = LIVE_STANDARDS.read_text(encoding="utf-8")

    assert "Suggested for this week" in source
    assert "weeklyLessons?: PlannedLessonContext[]" in source
    assert "weeklyLessons = []" in source
    assert "relevanceScore" in source
    assert "deterministic relevance matching, not AI-generated standards" in source
    assert "Browse all approved standards" in source
    assert "Search by code, wording, strand, or source" in source
    assert "Unit ${match[1]} · Chapter ${match[2]}" in source
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
    assert 'request[fieldToRegenerate] = ""' in planning
    assert "requestBaseDraft(field)" in planning
    assert "requestDistrictDraft()" in planning
    assert 'Authorization: `Bearer ${accessToken}`' in planning
    assert "Nothing is saved until you save your weekly plan" in planning
    assert "hasScheduledLessons" in planning
    assert "AI will not invent a weekly lesson sequence from standards alone" in planning


def test_weekly_reflection_is_required_and_entirely_teacher_authored() -> None:
    reflection = REFLECTION.read_text(encoding="utf-8")

    assert "Required teacher reflection" in reflection
    assert "Weekly Reflection / PLC Discussion" in reflection
    assert "TPP does not generate or rewrite these responses" in reflection
    assert "What knowledge has been building this week?" in reflection
    assert "What are next week's instructional priorities?" in reflection
    assert "Respond at the class or group level" in reflection
    assert "student names" in reflection
    assert "/api/v1/ai/reflection" not in reflection
    assert "Suggest Weekly Reflection" not in reflection


def test_planning_draft_covers_full_workflow_and_bulk_teacher_acceptance() -> None:
    source = PLANNING.read_text(encoding="utf-8")

    for field in (
        "unit_topic",
        "literacy_standards",
        "act_preparation",
        "learning_targets",
        "know",
        "understand",
        "do_statement",
        "activities",
        "assessments",
        "resources",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
    ):
        assert f'"{field}"' in source
    assert "Use all remaining suggestions" in source
    assert "tpp:standards-saved" in source
    assert "approved Alabama literacy standards" in source
    assert "governed ACT references" in source


def test_teacher_assistance_surfaces_preserve_no_student_data_boundary() -> None:
    planning = PLANNING.read_text(encoding="utf-8")
    reflection = REFLECTION.read_text(encoding="utf-8")

    assert "Do not enter student names" in planning
    assert 'role="note"' in planning
    assert 'aria-label="Student data restriction"' in planning
    assert 'role="alert"' in planning
    assert 'role="status"' in planning
    assert 'aria-live="polite"' in planning

    assert "Do not enter student names" in reflection
    assert 'role="note"' in reflection
    assert 'aria-label="Reflection data boundary"' in reflection
    assert 'role="status"' in reflection


def test_platform_admin_act_reference_review_is_human_controlled() -> None:
    act_admin = ACT_ADMIN.read_text(encoding="utf-8")
    standards_admin = STANDARDS_ADMIN.read_text(encoding="utf-8")

    assert "/api/v1/act-reference-admin/pending" in act_admin
    assert (
        "/api/v1/act-reference-admin/snapshots/${encodeURIComponent(snapshot.id)}/approve"
        in act_admin
    )
    assert 'Authorization: `Bearer ${accessToken}`' in act_admin
    assert "window.confirm" in act_admin
    assert "entry_count" in act_admin
    assert "benchmark_count" in act_admin
    assert "Inspect authoritative ACT source" in act_admin
    assert "Nothing is approved automatically" in act_admin
    assert 'from "./ActReferenceAdministrationPanel"' in standards_admin
    assert "<ActReferenceAdministrationPanel" in standards_admin


def test_gate_e_teacher_components_do_not_collect_student_specific_fields() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            COURSE_SETUP,
            MAPPING,
            CANONICAL_STANDARDS,
            LIVE_STANDARDS,
            PLANNING,
            REFLECTION,
            ACT_ADMIN,
        )
    ).lower()

    forbidden_form_terms = (
        'name="student',
        "student_id",
        "student_name",
        "student_email",
        "student_grade",
        "iep_field",
        "student_work=",
    )
    assert all(term not in combined for term in forbidden_form_terms)
