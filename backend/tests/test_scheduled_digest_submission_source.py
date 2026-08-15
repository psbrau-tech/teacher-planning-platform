from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815011000_friday_submission_status.sql"
)


def test_friday_status_reads_immutable_submissions_directly() -> None:
    source = STATUS_MIGRATION.read_text(encoding="utf-8")
    status_function = source.split(
        "create or replace function private.friday_assignment_status",
        maxsplit=1,
    )[1].split(
        "create or replace function public.teacher_friday_submission_status",
        maxsplit=1,
    )[0]

    assert "public.weekly_plan_snapshots" not in status_function
    assert "public.weekly_plan_submissions" in status_function
    assert "wps.teaching_assignment_id = ta.id" in status_function
    assert "wps.week_start = target_week_start" in status_function
    assert "wps.submission_kind = 'completed_packet'" in status_function
    assert "wps.week_start = (target_week_start + 7)::date" in status_function
    assert "wps.submission_kind = 'lesson_plan'" in status_function


def test_friday_status_source_comment_documents_newer_draft_safety() -> None:
    source = " ".join(STATUS_MIGRATION.read_text(encoding="utf-8").lower().split())

    assert "directly from immutable weekly_plan_submissions" in source
    assert "newer working draft" in source
    assert "already-submitted packet or lesson plan appear missing" in source
