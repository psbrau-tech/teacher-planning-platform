from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _payload(*, schedule_type: str = "period", curriculum_id: str | None = "jrotc-let-1") -> dict[str, object]:
    return {
        "school_id": "anniston-high-school",
        "course_name": "Army JROTC LET 1",
        "course_code": "JROTC-1",
        "curriculum_id": curriculum_id,
        "grade_band": "9-12",
        "meeting_patterns": [
            {
                "schedule_type": schedule_type,
                "weekdays": [1, 2, 3, 4, 5],
                "start_time": "08:00:00",
                "end_time": "08:50:00",
                "effective_start": "2026-08-10",
                "effective_end": "2027-05-28",
            }
        ],
    }


def test_teacher_can_create_list_and_reopen_assignment() -> None:
    headers = {"X-TPP-Teacher-ID": "teacher-alpha"}
    created = client.post("/api/v1/teaching-assignments", json=_payload(), headers=headers)

    assert created.status_code == 201
    record = created.json()
    assert record["teacher_id"] == "teacher-alpha"
    assert record["revision"] == 1
    assert record["meeting_patterns"][0]["schedule_type"] == "period"

    listed = client.get("/api/v1/teaching-assignments", headers=headers)
    reopened = client.get(
        f"/api/v1/teaching-assignments/{record['id']}",
        headers=headers,
    )

    assert listed.status_code == 200
    assert any(item["id"] == record["id"] for item in listed.json())
    assert reopened.status_code == 200
    assert reopened.json()["course_name"] == "Army JROTC LET 1"


def test_teacher_can_create_class_before_adding_curriculum() -> None:
    headers = {"X-TPP-Teacher-ID": "teacher-progressive-setup"}
    created = client.post(
        "/api/v1/teaching-assignments",
        json=_payload(curriculum_id=None),
        headers=headers,
    )

    assert created.status_code == 201
    assert created.json()["curriculum_id"] is None
    assert created.json()["course_name"] == "Army JROTC LET 1"


def test_teacher_can_update_schedule_with_revision_protection() -> None:
    headers = {"X-TPP-Teacher-ID": "teacher-bravo"}
    created = client.post("/api/v1/teaching-assignments", json=_payload(), headers=headers)
    assignment_id = created.json()["id"]

    payload = _payload(schedule_type="block")
    payload["expected_revision"] = 1
    updated = client.put(
        f"/api/v1/teaching-assignments/{assignment_id}",
        json=payload,
        headers=headers,
    )

    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["meeting_patterns"][0]["schedule_type"] == "block"

    stale = client.put(
        f"/api/v1/teaching-assignments/{assignment_id}",
        json=payload,
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "teaching assignment revision conflict"


def test_assignments_are_isolated_between_teachers() -> None:
    owner_headers = {"X-TPP-Teacher-ID": "teacher-charlie"}
    other_headers = {"X-TPP-Teacher-ID": "teacher-delta"}
    created = client.post(
        "/api/v1/teaching-assignments",
        json=_payload(),
        headers=owner_headers,
    )
    assignment_id = created.json()["id"]

    assert client.get(
        f"/api/v1/teaching-assignments/{assignment_id}",
        headers=other_headers,
    ).status_code == 404
    assert client.get(
        "/api/v1/teaching-assignments",
        headers=other_headers,
    ).json() == []


def test_assignment_requires_teacher_identity_and_valid_pattern() -> None:
    assert client.post("/api/v1/teaching-assignments", json=_payload()).status_code == 401

    invalid = _payload()
    invalid["meeting_patterns"] = []
    response = client.post(
        "/api/v1/teaching-assignments",
        json=invalid,
        headers={"X-TPP-Teacher-ID": "teacher-echo"},
    )
    assert response.status_code == 422
