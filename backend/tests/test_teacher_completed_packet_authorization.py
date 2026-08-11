from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260811030100_teacher_completed_packet_read.sql"
)
client = TestClient(app)


def test_completed_packet_requires_authenticated_teacher() -> None:
    response = client.get(
        "/api/v1/teacher-submissions/00000000-0000-0000-0000-000000000001/completed-packet",
        params={"week_start": "2026-08-10"},
    )
    assert response.status_code == 401


def test_completed_packet_rejects_non_monday_before_data_access() -> None:
    response = client.get(
        "/api/v1/teacher-submissions/00000000-0000-0000-0000-000000000001/completed-packet",
        headers={"X-TPP-Teacher-ID": "teacher-packet-auth-test"},
        params={"week_start": "2026-08-11"},
    )
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Week of must be a Monday")


def test_completed_packet_rpc_is_teacher_owned_and_does_not_broaden_table_reads() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "if (select auth.uid()) is null" in sql
    assert "wps.teacher_id = (select auth.uid())" in sql
    assert "wps.submission_kind = 'completed_packet'" in sql
    assert "grant execute" in sql
    assert "to authenticated" in sql
    assert "grant select on table public.weekly_plan_submissions" not in sql.lower()
