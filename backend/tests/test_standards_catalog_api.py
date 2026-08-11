from uuid import uuid4

from fastapi.testclient import TestClient

import app.standards_catalog_api as catalog_api
from app.main import app

client = TestClient(app)
HEADERS = {"X-TPP-Teacher-ID": "teacher-catalog-test"}
ASSIGNMENT_ID = uuid4()
CATEGORY_ID = uuid4()
COURSE_ID = uuid4()
TEACHER_ID = "teacher-catalog-test"


class FakeClient:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, object] | None, object]] = []

    def request(
        self,
        method: str,
        resource: str,
        *,
        params=None,
        payload=None,
        prefer=None,
    ) -> object:
        self.calls.append((method, resource, params, payload))
        return self.responses.get(resource, [])


def _category() -> dict[str, object]:
    return {
        "id": str(CATEGORY_ID),
        "category_key": "government_public_administration",
        "display_name": "Government & Public Administration",
        "category_type": "career_cluster",
        "sort_order": 100,
    }


def _course() -> dict[str, object]:
    return {
        "id": str(COURSE_ID),
        "category_id": str(CATEGORY_ID),
        "course_key": "army_jrotc_let_2",
        "display_name": "Army JROTC II",
        "source_course_code": "JROTC II",
        "grade_band": "9-12",
    }


def _assignment() -> dict[str, str]:
    return {"id": str(ASSIGNMENT_ID)}


def _install(monkeypatch, fake: FakeClient) -> None:
    monkeypatch.setattr(catalog_api, "_client", lambda identity, settings: fake)


def test_catalog_routes_require_teacher_identity() -> None:
    response = client.get("/api/v1/standards/catalog/categories")
    assert response.status_code == 401


def test_teacher_lists_subject_or_cluster_then_courses(monkeypatch) -> None:
    fake = FakeClient(
        {
            "standard_catalog_categories": [_category()],
            "standard_catalog_courses": [_course()],
        }
    )
    _install(monkeypatch, fake)

    categories = client.get(
        "/api/v1/standards/catalog/categories",
        headers=HEADERS,
    )
    courses = client.get(
        f"/api/v1/standards/catalog/categories/{CATEGORY_ID}/courses",
        headers=HEADERS,
    )

    assert categories.status_code == 200
    assert categories.json()[0]["display_name"] == "Government & Public Administration"
    assert categories.json()[0]["category_type"] == "career_cluster"
    assert courses.status_code == 200
    assert courses.json()[0]["display_name"] == "Army JROTC II"
    course_call = next(call for call in fake.calls if call[1] == "standard_catalog_courses")
    assert course_call[2]["category_id"] == f"eq.{CATEGORY_ID}"


def test_unmapped_assignment_reports_existing_plan_counts_without_forcing_warning(
    monkeypatch,
) -> None:
    fake = FakeClient(
        {
            "teaching_assignments": [_assignment()],
            "assignment_standard_courses": [],
            "weekly_plan_snapshots": [{"id": str(uuid4())}],
            "friday_validation_snapshots": [{"id": str(uuid4())}],
        }
    )
    _install(monkeypatch, fake)

    response = client.get(
        f"/api/v1/standards/assignment/{ASSIGNMENT_ID}/mapping",
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "assignment_id": str(ASSIGNMENT_ID),
        "mapped": False,
        "category": None,
        "course": None,
        "warning_required_for_change": False,
        "weekly_plan_count": 1,
        "validated_week_count": 1,
    }


def test_existing_mapping_reports_warning_requirement(monkeypatch) -> None:
    fake = FakeClient(
        {
            "teaching_assignments": [_assignment()],
            "assignment_standard_courses": [{"catalog_course_id": str(COURSE_ID)}],
            "weekly_plan_snapshots": [{"id": str(uuid4())}],
            "friday_validation_snapshots": [{"id": str(uuid4())}],
            "standard_catalog_courses": [_course()],
            "standard_catalog_categories": [_category()],
        }
    )
    _install(monkeypatch, fake)

    response = client.get(
        f"/api/v1/standards/assignment/{ASSIGNMENT_ID}/mapping",
        headers=HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mapped"] is True
    assert body["warning_required_for_change"] is True
    assert body["category"]["display_name"] == "Government & Public Administration"
    assert body["course"]["display_name"] == "Army JROTC II"


def test_mapping_save_uses_confirmed_atomic_rpc(monkeypatch) -> None:
    fake = FakeClient(
        {
            "teaching_assignments": [_assignment()],
            "rpc/set_assignment_standard_catalog_course": {
                "changed": True,
                "warning_required": True,
                "open_selection_count_cleared": 2,
                "validated_week_count_preserved": 4,
                "catalog_course_id": str(COURSE_ID),
            },
            "standard_catalog_courses": [_course()],
            "standard_catalog_categories": [_category()],
        }
    )
    _install(monkeypatch, fake)

    response = client.put(
        f"/api/v1/standards/assignment/{ASSIGNMENT_ID}/mapping",
        headers=HEADERS,
        json={
            "catalog_course_id": str(COURSE_ID),
            "confirm_existing_plans": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["changed"] is True
    assert body["open_selection_count_cleared"] == 2
    assert body["validated_week_count_preserved"] == 4
    rpc_call = next(
        call
        for call in fake.calls
        if call[1] == "rpc/set_assignment_standard_catalog_course"
    )
    assert rpc_call[3] == {
        "target_assignment_id": str(ASSIGNMENT_ID),
        "target_catalog_course_id": str(COURSE_ID),
        "confirm_existing_plans": True,
    }
