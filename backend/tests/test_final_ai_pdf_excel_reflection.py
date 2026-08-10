from pathlib import Path

from app.ai_district_planning_api import DISTRICT_FIELD_KEYS, DISTRICT_PLANNING_SCHEMA

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
MIGRATIONS = ROOT / "supabase" / "migrations"


def test_district_ai_schema_covers_all_framework_and_week_at_glance_fields() -> None:
    assert len(DISTRICT_FIELD_KEYS) == 35
    required = set(DISTRICT_PLANNING_SCHEMA["required"])
    assert set(DISTRICT_FIELD_KEYS).issubset(required)
    for field in (
        "plds",
        "misconceptions",
        "formative",
        "summative",
        "performance_task",
        "clt_mon",
        "rrt_mon",
        "cfu_mon",
        "ri_mon",
        "sic_mon",
        "esl_mon",
        "clt_fri",
        "esl_fri",
    ):
        assert field in required


def test_ai_planning_ui_integrates_district_suggestions_with_teacher_control() -> None:
    source = (FRONTEND / "AiPlanningPanel.tsx").read_text(encoding="utf-8")
    assert "/api/v1/ai/district-planning/" in source
    assert "Required governed literacy recommendation" in source
    assert 'label: "Instructional Planning Framework"' in source
    assert "Week at a Glance — Clear learning target & success criteria" in source
    assert "Week at a Glance — Evidence of student learning" in source
    assert "Use all remaining suggestions" in source
    assert "Use suggestion" in source
    assert "Use edited text" in source
    assert "Skip suggestion" in source
    assert "DISTRICT_FIELDS.map" in source


def test_ai_decision_migration_governs_district_planning_fields() -> None:
    migration = (
        MIGRATIONS / "20260810003300_expand_ai_district_planning_decision_fields.sql"
    ).read_text(encoding="utf-8")
    for field in (
        "plds",
        "misconceptions",
        "formative",
        "summative",
        "performance_task",
        "clt_mon",
        "cfu_tue",
        "ri_wed",
        "sic_thu",
        "esl_fri",
    ):
        assert f"'{field}'" in migration
    assert "record_ai_suggestion_decision" in migration


def test_excel_pacing_round_trip_is_browser_side_and_populates_lesson_cards() -> None:
    editor = (FRONTEND / "PacingSequenceEditor.tsx").read_text(encoding="utf-8")
    importer = (FRONTEND / "pacingWorkbookImport.ts").read_text(encoding="utf-8")
    assert "Load Excel pacing file" in editor
    assert "readPacingWorkbook" in editor
    excel_accept = (
        'accept=".xlsx,'
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"'
    )
    assert excel_accept in editor
    assert "DecompressionStream" in importer
    assert "xl/worksheets/sheet1.xml" in importer
    assert "Unit / Topic and Lesson / Focus columns" in importer
    contract = importer.split("type ZipEntry", maxsplit=1)[0]
    assert "standards" not in contract.lower()


def test_pdf_field_ui_explains_ai_assistance_and_teacher_review() -> None:
    source = (FRONTEND / "PlanningPdfFieldsPanel.tsx").read_text(encoding="utf-8")
    assert "The fields below follow the same sequence as the Weekly Lesson Plan PDF" in source
    assert "AI suggestions remain drafts until you use or edit them" in source
    assert "AI recommends cells only for scheduled instructional days" in source
    assert '<table className="week-at-glance-matrix">' in source
    assert "Performance-Level Descriptors / Proficiency Scale" in source
    assert "Strong instructional culture" in source
    assert "Evidence of student learning" in source


def test_friday_reflection_has_saved_pdf_preview_without_ai_generation() -> None:
    source = (FRONTEND / "AiReflectionPanel.tsx").read_text(encoding="utf-8")
    assert "View saved reflection PDF" in source
    assert "/api/v1/documents/anniston-hqi/weekly-reflection" in source
    assert "Save the Friday closeout before previewing" in source
    assert "pdf-modal-backdrop" in source
    assert "TPP does not generate or rewrite these responses" in source
    assert "/api/v1/ai/reflection" not in source
