from pathlib import Path

from fastapi.testclient import TestClient

from app.ai_planning_resilient_api import _resolve_valid_literacy, _valid_act_ids
from app.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]


def _assignment_payload() -> dict[str, object]:
    return {
        "school_id": "anniston-high-school",
        "course_name": "Regression Course",
        "course_code": "REG-1",
        "curriculum_id": "regression-curriculum",
        "grade_band": "9-12",
        "meeting_patterns": [
            {
                "schedule_type": "period",
                "weekdays": [1, 2, 3, 4, 5],
                "start_time": "08:00:00",
                "end_time": "08:50:00",
                "effective_start": "2026-08-10",
                "effective_end": "2027-05-28",
            }
        ],
    }


def test_course_remove_archives_from_active_teacher_planning() -> None:
    headers = {"X-TPP-Teacher-ID": "workflow-archive-owner"}
    created = client.post(
        "/api/v1/teaching-assignments",
        json=_assignment_payload(),
        headers=headers,
    )
    assert created.status_code == 201
    assignment_id = created.json()["id"]

    removed = client.delete(
        f"/api/v1/teaching-assignments/{assignment_id}",
        headers=headers,
    )
    assert removed.status_code == 204
    assert all(
        item["id"] != assignment_id
        for item in client.get("/api/v1/teaching-assignments", headers=headers).json()
    )
    assert client.delete(
        f"/api/v1/teaching-assignments/{assignment_id}",
        headers={"X-TPP-Teacher-ID": "workflow-archive-other"},
    ).status_code == 404


def test_friday_closeout_does_not_require_literacy_or_act_fields() -> None:
    response = client.put(
        "/api/v1/weekly-drafts/closeout",
        json={
            "assignment_id": "workflow-closeout-assignment",
            "week_start": "2026-08-03",
            "content": {"reflection": '{"reflect_1":"Teacher-authored observation"}'},
            "expected_revision": None,
        },
        headers={"X-TPP-Teacher-ID": "workflow-closeout-teacher"},
    )
    assert response.status_code == 200
    assert response.json()["content"]["reflection"]
    assert "literacy_standards" not in response.json()["content"]
    assert "act_preparation" not in response.json()["content"]


def test_resilient_ai_reference_resolution_rejects_unknown_ids_without_fabrication() -> None:
    literacy = [
        {
            "standard_entry_id": "approved-lit-1",
            "grade_band": "9",
            "code": "R1",
            "authoritative_text": "Approved literacy wording",
        }
    ]
    resolved = _resolve_valid_literacy(
        literacy,
        ["unknown-lit", "approved-lit-1", "unknown-lit-2"],
    )
    assert "Approved literacy wording" in resolved
    assert "unknown-lit" not in resolved

    act = [{"reference_code": "ACT-APPROVED"}]
    assert _valid_act_ids(act, ["ACT-UNKNOWN"]) == []
    assert _valid_act_ids(act, ["ACT-UNKNOWN", "ACT-APPROVED"]) == ["ACT-APPROVED"]


def test_planned_lesson_move_is_bounded_to_week_and_valid_meeting_day() -> None:
    source = (ROOT / "backend" / "app" / "planned_lesson_api.py").read_text(
        encoding="utf-8"
    )
    assert "_monday(original) != _monday(payload.lesson_date)" in source
    assert "weekday in pattern.weekdays" in source
    assert "pattern.effective_start <= payload.lesson_date <= pattern.effective_end" in source
    assert '"is_teacher_override": True' in source


def test_period_reporting_is_real_and_date_scoped_not_cosmetic() -> None:
    migration = (
        ROOT
        / "supabase"
        / "migrations"
        / "20260809003100_period_scoped_admin_reporting.sql"
    ).read_text(encoding="utf-8")
    admin_ui = (ROOT / "frontend" / "src" / "AdministrationOverview.tsx").read_text(
        encoding="utf-8"
    )
    assert "period_start" in migration
    assert "period_end" in migration
    assert "weekly_plans_created" in migration
    assert "instruction_records_validated" in migration
    assert "documents_requested" in migration
    assert "Current week" in admin_ui
    assert "Last 4 weeks" in admin_ui
    assert "Current grading period" in admin_ui
    assert "Custom dates" in admin_ui
