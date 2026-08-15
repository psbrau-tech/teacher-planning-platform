from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815011000_friday_submission_status.sql"
)


def test_friday_status_requires_teacher_governed_school_match() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    status_function = source.split(
        "create or replace function private.friday_assignment_status",
        maxsplit=1,
    )[1].split(
        "create or replace function public.teacher_friday_submission_status",
        maxsplit=1,
    )[0]

    assert "teacher.school_id = ta.school_id" in status_function
    assert "teacher_role.school_id = ta.school_id" in status_function
    assert "teacher_role.role = 'teacher'::public.app_role" in status_function
