from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
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


def test_live_weekly_selector_prioritizes_scheduled_lesson_relevance(
) -> None:
    source = LIVE_STANDARDS.read_text(encoding="utf-8")

    assert "Suggested for this week" in source
    assert "/api/v1/plans?assignment_id=" in source
    assert "relevanceScore" in source
    assert "deterministic relevance aid, not AI rewriting" in source
    assert "Browse all approved standards" in source
    assert "Search by code, wording, strand, or source" in source
    assert "Unit ${match[1]} · Chapter ${match[2]}" in source
    assert 'new CustomEvent("tpp:standards-saved"' in source


def test_weekly_plan_reaches_course_mapping_and_canonical_standards_selector() -> None:
    source = WEEKLY_CONTEXT.read_text(encoding="utf-8")

    assert 'from "./StandardsCourseMappingPanel"' in source
    assert 'from "./CanonicalStandardsPanel"' in source
    assert "<StandardsCourseMappingPanel" in source
    assert "<CanonicalStandardsPanel" in source
    assert "mappingRevision" in source
    assert "onMappingSaved" in source


def test_ai_planning_and_reflection_remain_teacher_reviewed_drafts() -> None:
    planning = PLANNING.read_text(encoding="utf-8")
    reflection = REFLECTION.read_text(encoding="utf-8")

    for source in (planning, reflection):
        assert "AI draft suggestion — not saved" in source
        assert "Accept as written" in source
        assert "Apply edited version" in source
        assert "Reject" in source
        assert 'Authorization: `Bearer ${accessToken}`' in source

    assert "Nothing has been added to your plan" in planning
    assert "Nothing has been added to your saved plan" in reflection
    assert "saved weekly plan, finalized Friday validation" in reflection


def test_integrated_planning_draft_covers_full_hqi_workflow_and_bulk_teacher_acceptance() -> None:
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
    assert "Apply full planning draft" in source
    assert "tpp:standards-saved" in source
    assert "approved Alabama literacy standards" in source
    assert "governed ACT reference catalog" in source


def test_ai_surfaces_show_no_student_data_notice_and_accessible_status() -> None:
    for path in (PLANNING, REFLECTION):
        source = path.read_text(encoding="utf-8")
        assert "Do not include student data." in source
        assert 'role="note"' in source
        assert 'aria-label="Student data restriction"' in source
        assert 'role="alert"' in source
        assert 'role="status"' in source
        assert 'aria-live="polite"' in source


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

    # Warning copy is required to name prohibited student-data categories. This
    # guard therefore targets actual form/API field identifiers rather than
    # treating the mandated notice itself as evidence that TPP collects them.
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
