from uuid import uuid4

from fastapi.testclient import TestClient

import app.schedule_exception_api as schedule_exception_api
from app.main import app

client = TestClient(app)
HEADERS = {"X-TPP-Teacher-ID": "teacher-api-test"}
ASSIGNMENT_ID = uuid4()
EXCEPTION_ID = uuid4()


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str] | None, object, str | None]] = []

    def request(
        self,
        method: str,
        resource: str,
        *,
        params: dict[str, str] | None = None,
        payload: object = None,
        prefer: str | None = None,
    ) -> object:
        self.calls.append((method, resource, params, payload, prefer))
        if method == "GET":
            return [
                {
                    "id": str(EXCEPTION_ID),
                    "teaching_assignment_id": str(ASSIGNMENT_ID),
                    "exception_date": "2026-08-13",
                    "is_available": False,
                    "instructional_minutes": None,
                    "reason": "Synthetic rally",
                }
            ]
        if method == "POST":
            assert isinstance(payload, dict)
            return [
                {
                    "id": str(EXCEPTION_ID),
                    "teaching_assignment_id": str(ASSIGNMENT_ID),
                    "exception_date": payload["exception_date"],
                    "is_available": payload["is_available"],
                    "instructional_minutes": payload["instructional_minutes"],
                    "reason": payload["reason"],
                }
            ]
        return None


def _install_fake(monkeypatch) -> FakeClient:
    fake = FakeClient()
    monkeypatch.setattr(schedule_exception_api, "_client", lambda identity, settings: fake)
    monkeypatch.setattr(
        schedule_exception_api,
        "_require_assignment",
        lambda client, identity, assignment_id: None,
    )
    return fake


def test_schedule_exception_requires_teacher_identity() -> None:
    response = client.put(
        f"/api/v1/schedule-exceptions/{ASSIGNMENT_ID}/2026-08-13",
        json={"is_available": False, "reason": "Synthetic rally"},
    )
    assert response.status_code == 401


def test_schedule_exception_upsert_is_assignment_scoped(monkeypatch) -> None:
    fake = _install_fake(monkeypatch)
    response = client.put(
        f"/api/v1/schedule-exceptions/{ASSIGNMENT_ID}/2026-08-13",
        headers=HEADERS,
        json={"is_available": False, "reason": "Synthetic rally"},
    )
    assert response.status_code == 200
    assert response.json()["exception_date"] == "2026-08-13"
    method, resource, params, payload, prefer = fake.calls[-1]
    assert method == "POST"
    assert resource == "schedule_exceptions"
    assert params == {"on_conflict": "teaching_assignment_id,exception_date"}
    assert payload["teaching_assignment_id"] == str(ASSIGNMENT_ID)
    assert payload["instructional_minutes"] is None
    assert prefer == "resolution=merge-duplicates,return=representation"


def test_available_exception_requires_instructional_minutes(monkeypatch) -> None:
    _install_fake(monkeypatch)
    response = client.put(
        f"/api/v1/schedule-exceptions/{ASSIGNMENT_ID}/2026-08-13",
        headers=HEADERS,
        json={"is_available": True, "reason": "Shortened schedule"},
    )
    assert response.status_code == 422


def test_schedule_exception_list_uses_week_range(monkeypatch) -> None:
    fake = _install_fake(monkeypatch)
    response = client.get(
        "/api/v1/schedule-exceptions",
        headers=HEADERS,
        params={"assignment_id": str(ASSIGNMENT_ID), "week_start": "2026-08-10"},
    )
    assert response.status_code == 200
    assert response.json()[0]["reason"] == "Synthetic rally"
    _, resource, params, _, _ = fake.calls[-1]
    assert resource == "schedule_exceptions"
    assert params is not None
    assert params["teaching_assignment_id"] == f"eq.{ASSIGNMENT_ID}"
    assert params["and"] == "(exception_date.gte.2026-08-10,exception_date.lte.2026-08-14)"


def test_schedule_exception_delete_is_assignment_and_date_scoped(monkeypatch) -> None:
    fake = _install_fake(monkeypatch)
    response = client.delete(
        f"/api/v1/schedule-exceptions/{ASSIGNMENT_ID}/2026-08-13",
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    method, resource, params, _, prefer = fake.calls[-1]
    assert method == "DELETE"
    assert resource == "schedule_exceptions"
    assert params == {
        "teaching_assignment_id": f"eq.{ASSIGNMENT_ID}",
        "exception_date": "eq.2026-08-13",
    }
    assert prefer == "return=minimal"
