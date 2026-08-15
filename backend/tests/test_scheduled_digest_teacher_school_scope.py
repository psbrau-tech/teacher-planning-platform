from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815011000_scheduled_admin_digest_worker.sql"
)


def test_scheduled_assignment_counts_require_teacher_governed_school_match() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    candidate_function = source.split(
        "create or replace function public.claim_scheduled_admin_weekly_digest_candidates",
        maxsplit=1,
    )[1].split(
        "create or replace function public.complete_scheduled_admin_weekly_digest_delivery",
        maxsplit=1,
    )[0]

    assert "teacher.school_id = ta.school_id" in candidate_function
    assert "teacher_role.school_id = ta.school_id" in candidate_function
    assert "teacher_role.role = 'teacher'::public.app_role" in candidate_function
