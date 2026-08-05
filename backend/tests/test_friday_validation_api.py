from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload(*, expected_revision: int | None = None, status: str = "completed"):
    assignment_id = str(uuid4())
    scheduled_lesson_id = str(uuid4())
    curriculum_lesson_id = str(uuid4())
    body = {
        "assignment_id": assignment_id,
        "week_start": "2026-08-10",
        "lessons": [
            {
                "scheduled_lesson_id": scheduled_lesson_id,
                "curriculum_lesson_id": curriculum_lesson_id,
                "lesson_date": "2026-08-10",
                "sequence": 1,
                "status": status,
                "reason": "Testing schedule" if status == "missed" else None,
                "teacher_note": "Validated during Friday review",
                "carry_forward": status == "missed",
            }
        ],
    }
    if expected_revision is not None:
        body["expected_revision"] = expected_revision
    return body


def test_friday_validation_requires_teacher_identity() -> None:
    response = client.put("/api/v1/friday-validations", json=payload())
    assert response.status_code == 401


def test_friday_validation_can_be_saved_and_reloaded() -> None:
    body = payload(status="missed")
    headers = {"X-TPP-Teacher-ID": "teacher-api-a"}

    saved = client.put("/api/v1/friday-validations", json=body, headers=headers)
    assert saved.status_code == 200
    result = saved.json()
    assert result["revision"] == 1
    assert result["missed_count"] == 1
    assert result["carry_forward_curriculum_lesson_ids"] == [
        body["lessons"][0]["curriculum_lesson_id"]
    ]

    loaded = client.get(
        "/api/v1/friday-validations",
        params={
            "assignment_id": body["assignment_id"],
            "week_start": body["week_start"],
        },
        headers=headers,
    )
    assert loaded.status_code == 200
    assert loaded.json() == result


def test_friday_validation_rejects_stale_revision() -> None:
    body = payload()
    headers = {"X-TPP-Teacher-ID": "teacher-api-b"}

    first = client.put("/api/v1/friday-validations", json=body, headers=headers)
    assert first.status_code == 200

    update = dict(body)
    update["expected_revision"] = 1
    second = client.put("/api/v1/friday-validations", json=update, headers=headers)
    assert second.status_code == 200
    assert second.json()["revision"] == 2

    stale = client.put("/api/v1/friday-validations", json=update, headers=headers)
    assert stale.status_code == 409
    assert "revision conflict" in stale.json()["detail"]


def test_friday_validation_is_teacher_isolated() -> None:
    body = payload()
    saved = client.put(
        "/api/v1/friday-validations",
        json=body,
        headers={"X-TPP-Teacher-ID": "teacher-api-c"},
    )
    assert saved.status_code == 200

    other_teacher = client.get(
        "/api/v1/friday-validations",
        params={
            "assignment_id": body["assignment_id"],
            "week_start": body["week_start"],
        },
        headers={"X-TPP-Teacher-ID": "teacher-api-d"},
    )
    assert other_teacher.status_code == 404
