from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
HEADERS = {"X-TPP-Teacher-ID": "teacher-api-test"}


def test_weekly_draft_requires_teacher_identity() -> None:
    response = client.put(
        "/api/v1/weekly-drafts",
        json={
            "assignment_id": "assignment-1",
            "week_start": "2026-08-10",
            "content": {"unit_topic": "Leadership"},
        },
    )
    assert response.status_code == 401


def test_weekly_draft_create_update_and_reload() -> None:
    created = client.put(
        "/api/v1/weekly-drafts",
        headers=HEADERS,
        json={
            "assignment_id": "assignment-1",
            "week_start": "2026-08-10",
            "content": {"unit_topic": "Leadership"},
        },
    )
    assert created.status_code == 200
    assert created.json()["revision"] == 1

    updated = client.put(
        "/api/v1/weekly-drafts",
        headers=HEADERS,
        json={
            "assignment_id": "assignment-1",
            "week_start": "2026-08-10",
            "content": {"unit_topic": "Leadership and followership"},
            "expected_revision": 1,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2

    loaded = client.get(
        "/api/v1/weekly-drafts",
        headers=HEADERS,
        params={
            "assignment_id": "assignment-1",
            "week_start": "2026-08-10",
        },
    )
    assert loaded.status_code == 200
    assert loaded.json()["content"]["unit_topic"] == "Leadership and followership"


def test_weekly_draft_rejects_stale_revision() -> None:
    response = client.put(
        "/api/v1/weekly-drafts",
        headers=HEADERS,
        json={
            "assignment_id": "assignment-1",
            "week_start": "2026-08-10",
            "content": {"unit_topic": "Stale edit"},
            "expected_revision": 1,
        },
    )
    assert response.status_code == 409
