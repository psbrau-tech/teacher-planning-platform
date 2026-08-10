from __future__ import annotations

import base64
import re
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
BACKEND_APP = ROOT / "backend" / "app"


def test_pacing_template_is_valid_xlsx_package() -> None:
    source = (FRONTEND / "pacingTemplate.ts").read_text(encoding="utf-8")
    match = re.search(r'PACING_TEMPLATE_BASE64 = "([A-Za-z0-9+/=]+)"', source)
    assert match is not None
    data = base64.b64decode(match.group(1))
    with ZipFile(BytesIO(data)) as workbook:
        assert workbook.testzip() is None
        names = set(workbook.namelist())
    assert "xl/workbook.xml" in names
    assert "xl/worksheets/sheet1.xml" in names


def test_pacing_setup_does_not_require_teacher_entered_standards() -> None:
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")
    editor = (FRONTEND / "PacingSequenceEditor.tsx").read_text(encoding="utf-8")
    assert "Standards family" not in setup
    assert 'name="standards_family"' not in setup
    assert "PacingSequenceEditor" in setup
    assert "Authoritative standards are selected later in Weekly Plan" in editor
    assert "event.currentTarget.reset" not in setup


def test_all_district_pdf_fields_are_teacher_editable() -> None:
    source = (FRONTEND / "PlanningPdfFieldsPanel.tsx").read_text(encoding="utf-8")
    for field in ("plds", "misconceptions", "formative", "summative", "performance_task"):
        assert f'"{field}"' in source
    for prefix in ("clt", "rrt", "cfu", "ri", "sic", "esl"):
        assert f'["{prefix}",' in source
    for suffix in ("mon", "tue", "wed", "thu", "fri"):
        assert f'["{suffix}",' in source


def test_weekly_plan_uses_combined_framework_and_grid_pdf() -> None:
    shell = (FRONTEND / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")
    main = (BACKEND_APP / "main.py").read_text(encoding="utf-8")
    service = (BACKEND_APP / "document_service.py").read_text(encoding="utf-8")
    assert ">Add class<" in shell
    assert "PlanningPdfFieldsPanel" in shell
    assert "/api/v1/documents/anniston-lesson-plan-packet" in shell
    assert "Instructional Planning Framework + Week at a Glance" in shell
    assert '@app.post("/api/v1/documents/anniston-lesson-plan-packet"' in main
    assert "generate_anniston_lesson_plan_packet" in service
