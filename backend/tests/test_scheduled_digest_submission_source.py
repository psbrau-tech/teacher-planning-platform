from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815011000_scheduled_admin_digest_worker.sql"
)


def test_scheduled_digest_counts_latest_immutable_submissions_directly() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    candidate_function = source.split(
        "create or replace function public.claim_scheduled_admin_weekly_digest_candidates",
        maxsplit=1,
    )[1].split(
        "create or replace function public.complete_scheduled_admin_weekly_digest_delivery",
        maxsplit=1,
    )[0]

    assert "public.weekly_plan_snapshots" not in candidate_function
    assert "wps.teaching_assignment_id = ta.id" in candidate_function
    assert "wps.week_start = target_week_start" in candidate_function
    assert "wps.submission_kind = 'lesson_plan'" in candidate_function
    assert "wps.submission_kind = 'completed_packet'" in candidate_function
    assert "order by wps.revision desc, wps.submitted_at desc" in candidate_function


def test_scheduled_digest_source_comment_documents_newer_draft_safety() -> None:
    source = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())

    assert "do not anchor these counts to the newest mutable weekly_plan_snapshot" in source
    assert "newer working snapshot after submitting an earlier revision" in source
    assert "already-submitted lesson plan or completed packet disappear" in source
