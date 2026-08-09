from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
MAIN = FRONTEND / "main.tsx"
CURRICULUM_ROWS = FRONTEND / "curriculumRows.ts"
MAPPING = FRONTEND / "StandardsCourseMappingPanel.tsx"
CANONICAL_STANDARDS = FRONTEND / "CanonicalStandardsPanel.tsx"
LIVE_STANDARDS = FRONTEND / "StandardsPanel.tsx"
PLANNING = FRONTEND / "AiPlanningPanel.tsx"
REFLECTION = FRONTEND / "AiReflectionPanel.tsx"
WEEKLY_CONTEXT = FRONTEND / "ScheduleExceptionPanel.tsx"
STANDARDS_ADMIN = FRONTEND / "StandardsAdministrationPanel.tsx"
ACT_ADMIN = FRONTEND / "ActReferenceAdministrationPanel.tsx"


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


def test_teacher_setup_uses_schedule_minutes_and_passes_live_week_to_standards() -> None:
    main = MAIN.read_text(encoding="utf-8")
    parser = CURRICULUM_ROWS.read_text(encoding="utf-8")

    assert 'from "./curriculumRows"' in main
    assert "parseCurriculumRows" in main
    assert "Leave minutes blank for normal lessons" in main
    assert "Minutes come from the course schedule." in main
    assert "weeklyLessons={plan}" in main
    assert "Optional minutes override" in main
    assert "estimated_minutes: number | null" in parser
    assert "if (!value.trim()) return null" in parser
    assert "previous pilot format" in parser


def test_weekly_plan_reaches_course_mapping_and_canonical_standards_selector() -> None:
    source = WEEKLY_CONTEXT.read_text(encoding="utf-8")

    assert 'from "./StandardsCourseMappingPanel"' in source
    assert 'from "./CanonicalStandardsPanel"' in source
    assert "<StandardsCourseMappingPanel" in source
    assert "<CanonicalStandardsPanel" in source
    assert "mappingRevision" in source
    assert "onMappingSaved" in source


def test_ai_planning_remains_teacher_reviewed_and_recoverable() -> None:
    planning = PLANNING.read_text(encoding="utf-8")

    assert "Suggested text — not saved" in planning
    assert "Use suggestion" in planning
    assert "Use edited text" in planning
    assert "Skip suggestion" in planning
    assert "Generate another suggestion" in planning
    assert "Use all remaining suggestions" in planning
    assert "fieldToRegenerate?: PlanningFieldKey" in planning
    assert '{ ...currentFields, [fieldToRegenerate]: "" }' in planning
    assert "requestDraft(field)" in planning
    assert 'Authorization: `Bearer ${accessToken}`' in planning
    assert "Nothing is saved until you save your weekly plan" in planning
    assert "estimated_cost_usd" in planning
    assert "Estimated request cost" not in planning


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
