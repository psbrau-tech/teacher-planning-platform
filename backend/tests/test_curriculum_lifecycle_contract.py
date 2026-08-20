from base64 import b64decode
from io import BytesIO
from pathlib import Path
import re
from xml.etree import ElementTree
from zipfile import ZipFile

from app.curriculum_api import (
    CurriculumDetailRead,
    CurriculumLessonRead,
    _contiguous_unit_groups,
    _same_locked_content,
    _StoredLesson,
    _xlsx_bytes,
)
from app.curriculum_import import CurriculumLessonImport

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
MIGRATIONS = ROOT / "supabase" / "migrations"


def _imported(sequence: int, unit: str, lesson: str) -> CurriculumLessonImport:
    return CurriculumLessonImport(
        sequence=sequence,
        unit_title=unit,
        lesson_title=lesson,
        estimated_minutes=None,
        standards=(),
        learning_targets=(),
        assessment="",
        can_split=False,
    )


def test_saved_curriculum_export_is_a_real_xlsx_with_current_rows() -> None:
    detail = CurriculumDetailRead(
        id="00000000-0000-0000-0000-000000000001",
        school_id="00000000-0000-0000-0000-000000000002",
        name="LET 1 Curriculum & Pacing",
        version="2026-27",
        standards_family=None,
        is_active=True,
        lessons=[
            CurriculumLessonRead(
                sequence=1,
                unit_title="Foundations",
                lesson_title="Introduction to JROTC",
                estimated_minutes=None,
                standards=[],
                learning_targets=["Explain the JROTC mission"],
                assessment="Exit ticket",
                can_split=False,
            ),
            CurriculumLessonRead(
                sequence=2,
                unit_title="Foundations",
                lesson_title="Cadet responsibilities",
                estimated_minutes=75,
                standards=[],
                learning_targets=["Describe cadet responsibilities"],
                assessment="Discussion check",
                can_split=False,
            ),
        ],
        active_class_count=2,
        locked_through_sequence=1,
    )
    workbook = _xlsx_bytes(detail)
    with ZipFile(BytesIO(workbook)) as archive:
        assert archive.testzip() is None
        assert "[Content_Types].xml" in archive.namelist()
        assert "xl/workbook.xml" in archive.namelist()
        workbook_xml = archive.read("xl/workbook.xml")
        sheet_xml = archive.read("xl/worksheets/sheet1.xml")
    workbook_root = ElementTree.fromstring(workbook_xml)
    ElementTree.fromstring(sheet_xml)
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    sheet_node = workbook_root.find(f"{namespace}sheets/{namespace}sheet")
    assert sheet_node is not None
    assert sheet_node.attrib["name"] == "Curriculum & Pacing"
    sheet = sheet_xml.decode("utf-8")
    assert "Introduction to JROTC" in sheet
    assert "Cadet responsibilities" in sheet
    assert "Optional Minutes Override" not in sheet
    assert "75" not in sheet


def test_downloadable_pacing_template_has_no_minutes_column() -> None:
    source = (FRONTEND / "pacingTemplate.ts").read_text(encoding="utf-8")
    encoded = re.search(r'PACING_TEMPLATE_BASE64 = "([^"]+)"', source)
    assert encoded is not None

    with ZipFile(BytesIO(b64decode(encoded.group(1)))) as archive:
        assert archive.testzip() is None
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")

    assert "Unit / Topic" in sheet
    assert "Lesson / Focus" in sheet
    assert "Learning Target(s)" in sheet
    assert "Assessment / Evidence" in sheet
    assert "Minutes" not in sheet


def test_noncontiguous_repeated_unit_titles_preserve_teacher_sequence() -> None:
    groups = _contiguous_unit_groups(
        (
            _imported(1, "Drill", "Facing movements"),
            _imported(2, "Leadership", "Team roles"),
            _imported(3, "Drill", "Column movements"),
        )
    )

    assert [title for title, _lessons in groups] == ["Drill", "Leadership", "Drill"]
    assert [
        lesson.sequence
        for _title, unit_lessons in groups
        for lesson in unit_lessons
    ] == [1, 2, 3]


def test_locked_curriculum_comparison_ignores_retired_minutes_and_split_fields() -> None:
    stored = _StoredLesson(
        sequence=1,
        unit_title="Introduction",
        lesson_title="Course orientation and expectations",
        estimated_minutes=50,
        standards=(),
        learning_targets=("Explain course expectations",),
        assessment="Exit ticket",
        can_split=True,
    )
    reconstructed = CurriculumLessonImport(
        sequence=1,
        unit_title="Introduction",
        lesson_title="Course orientation and expectations",
        estimated_minutes=None,
        standards=(),
        learning_targets=("Explain course expectations",),
        assessment="Exit ticket",
        can_split=False,
    )

    assert _same_locked_content(stored, reconstructed)
    assert not _same_locked_content(
        stored,
        CurriculumLessonImport(
            sequence=1,
            unit_title="Introduction",
            lesson_title="Changed teacher-visible title",
            estimated_minutes=50,
            standards=(),
            learning_targets=("Explain course expectations",),
            assessment="Exit ticket",
            can_split=False,
        ),
    )


def test_pacing_ui_and_exports_use_one_lesson_per_class_day() -> None:
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")
    editor = (FRONTEND / "PacingSequenceEditor.tsx").read_text(encoding="utf-8")
    importer = (FRONTEND / "pacingWorkbookImport.ts").read_text(encoding="utf-8")
    parser = (FRONTEND / "curriculumRows.ts").read_text(encoding="utf-8")
    api = (ROOT / "backend" / "app" / "curriculum_api.py").read_text(encoding="utf-8")

    assert "Each pacing lesson equals one day of class." in setup
    assert "Each pacing lesson equals one day of class." in editor
    assert "Optional minutes override" not in editor
    assert "Minutes override" not in editor
    assert "minutesColumn" not in importer
    assert "estimated_minutes: null" in parser
    assert '"Optional Minutes Override"' not in api


def test_current_year_curriculum_edit_uses_copy_on_write_and_teacher_owned_switch() -> None:
    api = (ROOT / "backend" / "app" / "curriculum_api.py").read_text(encoding="utf-8")
    migration = (
        MIGRATIONS / "20260811030400_teacher_curriculum_revision_switch.sql"
    ).read_text(encoding="utf-8")
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")

    assert '@router.put("/{curriculum_id}/pacing"' in api
    assert "revised = _save_curriculum(" in api
    assert 'rpc/replace_teacher_curriculum_version' in api
    assert "locked_through_sequence" in api
    assert "teacher-editable fields" in api
    assert "scheduled or submitted" in api
    assert "Edit current curriculum" in setup
    assert "Update shared future pacing" in setup
    assert "Create a separate copy for this class" in setup
    assert "Download Excel" in setup
    assert "Create new version / copy" in setup
    assert "Start with a complete first instructional week" in setup
    assert "Updating Course Setup" in setup
    assert "If multiple active classes reuse it" in setup

    assert "where c.id = prior_curriculum_id" in migration
    assert "c.created_by = (select auth.uid())" in migration
    assert "where teacher_id = (select auth.uid())" in migration
    assert "and is_active" in migration
    assert "teacher_curriculum_revision_activated" in migration
    assert "grant execute" in migration
    assert "to authenticated" in migration


def test_weekly_build_requires_explicit_curriculum_confirmation_and_closeout_recovers() -> None:
    shell = (FRONTEND / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")
    schedule = (FRONTEND / "ScheduleExceptionPanel.tsx").read_text(encoding="utf-8")
    admin = (FRONTEND / "AdminSubmissionPanel.tsx").read_text(encoding="utf-8")

    assert "const [weekCurriculumConfirmed, setWeekCurriculumConfirmed]" in shell
    assert "const weekStep1 = plan.length > 0 && weekCurriculumConfirmed" in shell
    assert "Confirm this week's curriculum & continue" in shell
    assert "Nothing advances to standards until you confirm this sequence" in shell
    assert "setWeekCurriculumConfirmed(false)" in shell

    assert 'document === "lesson-plan" && action === "view"' in shell
    assert '"View PDF & continue"' not in shell
    assert "Viewing the PDF only completes this review step" in shell
    assert "submission remains a separate Step 6 action" in shell
    assert "Reviewing the PDF did not submit it again" in shell

    assert "No class / postpone pacing for this day" in schedule
    assert "does not consume a pacing lesson" in schedule
    assert "Build / reconcile week" in schedule

    assert "teacherFilterRef" in admin
    assert "closeTeacherFilterOnOutsidePointer" in admin
    assert 'addEventListener("pointerdown"' in admin

    assert 'view !== "validation"' in shell
    assert "/completed-packet?week_start=" in shell
    assert "This Friday closeout was already submitted" in shell
    assert "setCompletedPacketSubmitted(true)" in shell
    assert "setCompletedPacketReviewed(false)" in shell
