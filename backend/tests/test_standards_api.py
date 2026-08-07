from uuid import UUID, uuid4

from fastapi.testclient import TestClient

import app.standards_api as standards_api
from app.auth import AuthenticatedTeacher, require_platform_admin
from app.main import app

client = TestClient(app)
HEADERS = {"X-TPP-Teacher-ID": "teacher-standards-test"}
ASSIGNMENT_ID = uuid4()
SOURCE_ID = uuid4()
COURSE_ID = uuid4()
SNAPSHOT_ID = uuid4()
ENTRY_ONE = uuid4()
ENTRY_TWO = uuid4()
ADMIN_ID = uuid4()


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


def _install_teacher_fake(monkeypatch, fake: FakeClient) -> None:
    monkeypatch.setattr(standards_api, "_client", lambda identity, settings: fake)
    monkeypatch.setattr(
        standards_api,
        "_require_assignment",
        lambda client, identity, assignment_id: None,
    )


def _mapping() -> dict[str, str]:
    return {
        "teaching_assignment_id": str(ASSIGNMENT_ID),
        "source_id": str(SOURCE_ID),
        "course_id": str(COURSE_ID),
        "mapped_by": str(ADMIN_ID),
    }


def test_standards_assignment_requires_teacher_identity() -> None:
    response = client.get(
        f"/api/v1/standards/assignment/{ASSIGNMENT_ID}",
        params={"week_start": "2026-08-10"},
    )

    assert response.status_code == 401


def test_unmapped_assignment_returns_bounded_empty_state(monkeypatch) -> None:
    fake = FakeClient({"assignment_standard_courses": []})
    _install_teacher_fake(monkeypatch, fake)

    response = client.get(
        f"/api/v1/standards/assignment/{ASSIGNMENT_ID}",
        params={"week_start": "2026-08-10"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "assignment_id": str(ASSIGNMENT_ID),
        "week_start": "2026-08-10",
        "mapped": False,
        "source": None,
        "course": None,
        "standards": [],
        "selected_entry_ids": [],
    }


def test_mapped_assignment_returns_only_approved_course_snapshot(monkeypatch) -> None:
    fake = FakeClient(
        {
            "assignment_standard_courses": [_mapping()],
            "standard_sources": [
                {
                    "id": str(SOURCE_ID),
                    "source_key": "army_jrotc_v12",
                    "authority": "U.S. Army Cadet Command",
                    "title": "Army JROTC Curriculum Guide",
                    "edition": "JROTC Curriculum Guide v12 (25 JUN 2025)",
                    "landing_url": "https://usarmyjrotc.army.mil/jsocc-course-documents/",
                    "approved_snapshot_id": str(SNAPSHOT_ID),
                }
            ],
            "standard_courses": [
                {
                    "id": str(COURSE_ID),
                    "source_id": str(SOURCE_ID),
                    "course_key": "army_jrotc_let_2",
                    "display_name": "Army JROTC LET 2",
                    "source_course_code": "LET 2",
                    "grade_band": "9-12",
                    "is_pilot_allowed": True,
                }
            ],
            "standard_snapshots": [
                {
                    "id": str(SNAPSHOT_ID),
                    "source_version": "v12",
                    "retrieved_at": "2026-08-07T20:00:00+00:00",
                    "resolved_document_url": (
                        "https://usarmyjrotc.army.mil/wp-content/uploads/2025/07/"
                        "JROTC-Curriculum-Guide-25JUN25-4.docx"
                    ),
                }
            ],
            "standard_entries": [
                {
                    "id": str(ENTRY_ONE),
                    "code": "U2C1L1",
                    "text": "Leadership foundations",
                    "parent_code": None,
                    "strand": None,
                    "sequence": 1,
                },
                {
                    "id": str(ENTRY_TWO),
                    "code": "U2C1L2",
                    "text": "Team roles",
                    "parent_code": None,
                    "strand": None,
                    "sequence": 2,
                },
            ],
            "weekly_standard_selections": [{"standard_entry_id": str(ENTRY_TWO)}],
        }
    )
    _install_teacher_fake(monkeypatch, fake)

    response = client.get(
        f"/api/v1/standards/assignment/{ASSIGNMENT_ID}",
        params={"week_start": "2026-08-10"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mapped"] is True
    assert body["source"]["authority"] == "U.S. Army Cadet Command"
    assert body["source"]["source_version"] == "v12"
    assert body["course"]["course_key"] == "army_jrotc_let_2"
    assert [item["code"] for item in body["standards"]] == ["U2C1L1", "U2C1L2"]
    assert body["selected_entry_ids"] == [str(ENTRY_TWO)]

    entries_call = next(call for call in fake.calls if call[1] == "standard_entries")
    assert entries_call[2]["snapshot_id"] == f"eq.{SNAPSHOT_ID}"
    assert entries_call[2]["course_id"] == f"eq.{COURSE_ID}"


def test_weekly_selection_uses_atomic_rpc(monkeypatch) -> None:
    fake = FakeClient({"rpc/replace_weekly_standard_selections": 2})
    _install_teacher_fake(monkeypatch, fake)

    response = client.put(
        f"/api/v1/standards/assignment/{ASSIGNMENT_ID}/week/2026-08-10",
        headers=HEADERS,
        json={"standard_entry_ids": [str(ENTRY_ONE), str(ENTRY_TWO)]},
    )

    assert response.status_code == 200
    assert response.json() == {"selected_count": 2}
    rpc_call = fake.calls[-1]
    assert rpc_call[0] == "POST"
    assert rpc_call[1] == "rpc/replace_weekly_standard_selections"
    assert rpc_call[3] == {
        "target_assignment_id": str(ASSIGNMENT_ID),
        "target_week_start": "2026-08-10",
        "target_entry_ids": [str(ENTRY_ONE), str(ENTRY_TWO)],
    }


def test_platform_admin_mapping_requires_platform_admin_role(monkeypatch) -> None:
    fake = FakeClient(
        {
            "teaching_assignments": [{"id": str(ASSIGNMENT_ID)}],
            "assignment_standard_courses": [_mapping()],
        }
    )
    monkeypatch.setattr(standards_api, "_client", lambda identity, settings: fake)

    denied = client.put(
        f"/api/v1/standards/admin/assignments/{ASSIGNMENT_ID}/mapping",
        headers=HEADERS,
        json={"source_id": str(SOURCE_ID), "course_id": str(COURSE_ID)},
    )
    assert denied.status_code == 403

    def test_admin() -> AuthenticatedTeacher:
        return AuthenticatedTeacher(
            subject=str(ADMIN_ID),
            email="admin@example.test",
            display_name="Pilot Admin",
            school_id=str(uuid4()),
            roles=frozenset({"platform_admin"}),
        )

    app.dependency_overrides[require_platform_admin] = test_admin
    try:
        allowed = client.put(
            f"/api/v1/standards/admin/assignments/{ASSIGNMENT_ID}/mapping",
            json={"source_id": str(SOURCE_ID), "course_id": str(COURSE_ID)},
        )
    finally:
        app.dependency_overrides.pop(require_platform_admin, None)

    assert allowed.status_code == 200
    assert UUID(allowed.json()["course_id"]) == COURSE_ID
    mapping_call = next(call for call in fake.calls if call[1] == "assignment_standard_courses")
    assert mapping_call[3]["mapped_by"] == str(ADMIN_ID)
