from uuid import uuid4

from fastapi.testclient import TestClient

import app.standards_api as standards_api
from app.main import app

client = TestClient(app)
HEADERS = {"X-TPP-Teacher-ID": "teacher-standards-test"}
ASSIGNMENT_ID = uuid4()
CATEGORY_ID = uuid4()
CATALOG_COURSE_ID = uuid4()
ALABAMA_SOURCE_ID = uuid4()
ARMY_SOURCE_ID = uuid4()
ALABAMA_COURSE_ID = uuid4()
ARMY_COURSE_ID = uuid4()
ALABAMA_SNAPSHOT_ID = uuid4()
ARMY_SNAPSHOT_ID = uuid4()
ENTRY_ONE = uuid4()
ENTRY_TWO = uuid4()


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
        "catalog_course_id": str(CATALOG_COURSE_ID),
        "mapped_by": str(uuid4()),
        "mapped_at": "2026-08-07T20:00:00+00:00",
    }


def _category() -> dict[str, object]:
    return {
        "id": str(CATEGORY_ID),
        "category_key": "government_public_administration",
        "display_name": "Government & Public Administration",
        "category_type": "career_cluster",
        "sort_order": 100,
    }


def _catalog_course() -> dict[str, object]:
    return {
        "id": str(CATALOG_COURSE_ID),
        "category_id": str(CATEGORY_ID),
        "course_key": "army_jrotc_let_2",
        "display_name": "Army JROTC II",
        "source_course_code": "JROTC II",
        "grade_band": "9-12",
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
    body = response.json()
    assert body["assignment_id"] == str(ASSIGNMENT_ID)
    assert body["mapped"] is False
    assert body["source"] is None
    assert body["sources"] == []
    assert body["catalog_category"] is None
    assert body["catalog_course"] is None
    assert body["standards"] == []
    assert body["selected_entry_ids"] == []


def test_mapped_assignment_aggregates_only_linked_approved_sources(monkeypatch) -> None:
    fake = FakeClient(
        {
            "assignment_standard_courses": [_mapping()],
            "standard_catalog_courses": [_catalog_course()],
            "standard_catalog_categories": [_category()],
            "standard_catalog_course_sources": [
                {
                    "source_course_id": str(ALABAMA_COURSE_ID),
                    "relationship": "primary",
                    "priority": 10,
                },
                {
                    "source_course_id": str(ARMY_COURSE_ID),
                    "relationship": "supplemental_authority",
                    "priority": 50,
                },
            ],
            "standard_courses": [
                {
                    "id": str(ALABAMA_COURSE_ID),
                    "source_id": str(ALABAMA_SOURCE_ID),
                    "course_key": "army_jrotc_let_2",
                    "display_name": "Army JROTC II",
                    "source_course_code": "JROTC II",
                    "grade_band": "9-12",
                    "is_pilot_allowed": True,
                },
                {
                    "id": str(ARMY_COURSE_ID),
                    "source_id": str(ARMY_SOURCE_ID),
                    "course_key": "army_jrotc_let_2",
                    "display_name": "Army JROTC LET 2",
                    "source_course_code": "LET 2",
                    "grade_band": "9-12",
                    "is_pilot_allowed": True,
                },
            ],
            "standard_sources": [
                {
                    "id": str(ALABAMA_SOURCE_ID),
                    "source_key": "alabama_jrotc_program",
                    "authority": "Alabama State Department of Education",
                    "title": "Government & Public Administration Program Guide",
                    "edition": "2025-2026",
                    "landing_url": "https://www.alabamaachieves.org/cte/",
                    "approved_snapshot_id": str(ALABAMA_SNAPSHOT_ID),
                },
                {
                    "id": str(ARMY_SOURCE_ID),
                    "source_key": "army_jrotc_v12",
                    "authority": "U.S. Army Cadet Command",
                    "title": "Army JROTC Curriculum Guide",
                    "edition": "JROTC Curriculum Guide v12 (25 JUN 2025)",
                    "landing_url": "https://usarmyjrotc.army.mil/jsocc-course-documents/",
                    "approved_snapshot_id": str(ARMY_SNAPSHOT_ID),
                },
            ],
            "standard_snapshots": [
                {
                    "id": str(ALABAMA_SNAPSHOT_ID),
                    "source_id": str(ALABAMA_SOURCE_ID),
                    "source_version": "2025-2026",
                    "retrieved_at": "2026-08-07T20:00:00+00:00",
                    "resolved_document_url": "https://www.alabamaachieves.org/example-jrotc.pdf",
                },
                {
                    "id": str(ARMY_SNAPSHOT_ID),
                    "source_id": str(ARMY_SOURCE_ID),
                    "source_version": "v12",
                    "retrieved_at": "2026-08-07T20:01:00+00:00",
                    "resolved_document_url": (
                        "https://usarmyjrotc.army.mil/wp-content/uploads/2025/07/"
                        "JROTC-Curriculum-Guide-25JUN25-4.docx"
                    ),
                },
            ],
            "standard_entries": [
                {
                    "id": str(ENTRY_ONE),
                    "snapshot_id": str(ALABAMA_SNAPSHOT_ID),
                    "course_id": str(ALABAMA_COURSE_ID),
                    "code": "JROTC-II",
                    "text": "Alabama JROTC II course alignment",
                    "parent_code": None,
                    "strand": None,
                    "sequence": 1,
                },
                {
                    "id": str(ENTRY_TWO),
                    "snapshot_id": str(ARMY_SNAPSHOT_ID),
                    "course_id": str(ARMY_COURSE_ID),
                    "code": "U2C1L1",
                    "text": "Leadership foundations",
                    "parent_code": None,
                    "strand": None,
                    "sequence": 1,
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
    assert body["catalog_category"]["display_name"] == "Government & Public Administration"
    assert body["catalog_course"]["display_name"] == "Army JROTC II"
    assert [source["relationship"] for source in body["sources"]] == [
        "primary",
        "supplemental_authority",
    ]
    assert [item["code"] for item in body["standards"]] == ["JROTC-II", "U2C1L1"]
    assert body["standards"][0]["authority"] == "Alabama State Department of Education"
    assert body["standards"][1]["authority"] == "U.S. Army Cadet Command"
    assert body["selected_entry_ids"] == [str(ENTRY_TWO)]

    entries_call = next(call for call in fake.calls if call[1] == "standard_entries")
    assert str(ALABAMA_COURSE_ID) in entries_call[2]["course_id"]
    assert str(ARMY_COURSE_ID) in entries_call[2]["course_id"]


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
