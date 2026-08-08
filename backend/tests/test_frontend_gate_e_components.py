from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
MAPPING = FRONTEND / "StandardsCourseMappingPanel.tsx"
STANDARDS = FRONTEND / "CanonicalStandardsPanel.tsx"
PLANNING = FRONTEND / "AiPlanningPanel.tsx"
REFLECTION = FRONTEND / "AiReflectionPanel.tsx"


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
    standards = STANDARDS.read_text(encoding="utf-8")

    assert 'Authorization: `Bearer ${accessToken}`' in mapping
    assert 'Authorization: `Bearer ${accessToken}`' in standards
    assert "catalog_course_id" in mapping
    assert "standard_entry_ids" in standards


def test_weekly_standard_selector_shows_canonical_course_and_exact_source_provenance() -> None:
    source = STANDARDS.read_text(encoding="utf-8")

    assert "catalog_category" in source
    assert "catalog_course" in source
    assert "sources: StandardSource[]" in source
    assert "Supplemental authority" in source
    assert "View authoritative source" in source
    assert "exact standard entry" in source
    assert "AI cannot rewrite authoritative wording" in source
    assert "Search by code, wording, strand, or source" in source


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


def test_gate_e_teacher_components_do_not_collect_student_specific_fields() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (MAPPING, STANDARDS, PLANNING, REFLECTION)
    ).lower()

    forbidden_form_terms = (
        'name="student',
        'student_id',
        'student name',
        'iep field',
    )
    assert all(term not in combined for term in forbidden_form_terms)
