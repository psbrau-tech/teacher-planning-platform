from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from app.curriculum_api import (
    CurriculumDetailRead,
    CurriculumLessonRead,
    _contiguous_unit_groups,
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
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "Introduction to JROTC" in sheet
    assert "Cadet responsibilities" in sheet
    assert "Optional Minutes Override" in sheet
    assert "75" in sheet


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


def test_blank_pacing_minutes_are_persisted_as_schedule_derived() -> None:
    migration = (
        MIGRATIONS / "20260811030300_curriculum_pacing_optional_minutes.sql"
    ).read_text(encoding="utf-8")
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")
    assert "alter column estimated_minutes drop not null" in migration.lower()
    assert "NULL means use the teaching assignment schedule" in migration
    assert "Leave the optional minutes override blank to use the saved class schedule" in setup


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
    assert "Edit current curriculum" in setup
    assert "Update shared future pacing" in setup
    assert "Create a separate copy for this class" in setup
    assert "Download Excel" in setup
    assert "Create new version / copy" in setup

    assert "where c.id = prior_curriculum_id" in migration
    assert "c.created_by = (select auth.uid())" in migration
    assert "where teacher_id = (select auth.uid())" in migration
    assert "and is_active" in migration
    assert "teacher_curriculum_revision_activated" in migration
    assert "grant execute" in migration
    assert "to authenticated" in migration


def test_weekly_build_requires_explicit_curriculum_confirmation_and_closeout_recovers() -> None:
    shell = (FRONTEND / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")
    assert "const [weekCurriculumConfirmed, setWeekCurriculumConfirmed]" in shell
    assert "const weekStep1 = plan.length > 0 && weekCurriculumConfirmed" in shell
    assert "Confirm this week's curriculum & continue" in shell
    assert "Nothing advances to standards until you confirm this sequence" in shell
    assert "setWeekCurriculumConfirmed(false)" in shell

    assert 'view !== "validation"' in shell
    assert "/completed-packet?week_start=" in shell
    assert "This Friday closeout was already submitted" in shell
    assert "setCompletedPacketSubmitted(true)" in shell
    assert "setCompletedPacketReviewed(false)" in shell
