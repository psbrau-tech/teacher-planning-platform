from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815011000_scheduled_admin_digest_worker.sql"
)


def test_scheduled_school_admin_recipient_matches_profile_governed_school() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    candidate_function = source.split(
        "create or replace function public.claim_scheduled_admin_weekly_digest_candidates",
        maxsplit=1,
    )[1].split(
        "create or replace function public.complete_scheduled_admin_weekly_digest_delivery",
        maxsplit=1,
    )[0]

    assert "p.school_id = pr.school_id" in candidate_function
    assert "pr.role = 'school_admin'::public.app_role" in candidate_function
    assert "p.is_active" in candidate_function
    assert "lower(btrim(p.email))" in candidate_function
