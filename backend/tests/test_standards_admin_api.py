from uuid import uuid4

from fastapi.testclient import TestClient

from app import standards_admin_api
from app.auth import AuthenticatedTeacher, require_platform_admin
from app.main import app

client = TestClient(app)
PLATFORM_ADMIN_ID = uuid4()
SCHOOL_ID = uuid4()
SOURCE_ID = uuid4()
SNAPSHOT_ID = uuid4()
RUN_ID = uuid4()
ITEM_ID = uuid4()


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object, object]] = []

    def request(self, method, resource, *, params=None, payload=None, prefer=None):
        self.calls.append((method, resource, params, payload))
        if resource == "standard_sources":
            if params and "id" in params:
                return [
                    {
                        "id": str(SOURCE_ID),
                        "source_key": "alabama_academic_science",
                        "title": "2023 Alabama Course of Study: Science",
                        "source_kind": "course_of_study",
                    }
                ]
            return [
                {
                    "id": str(SOURCE_ID),
                    "source_key": "alabama_academic_science",
                    "family": "alabama_academic",
                    "authority": "Alabama State Department of Education",
                    "title": "2023 Alabama Course of Study: Science",
                    "edition": "2023",
                    "source_kind": "course_of_study",
                    "provides_standard_entries": True,
                    "discovery_status": "pending",
                    "approved_snapshot_id": None,
                    "catalog_category_key": "science",
                    "catalog_category_name": "Science",
                }
            ]
        if resource == "standard_snapshots":
            return [
                {
                    "id": str(SNAPSHOT_ID),
                    "source_id": str(SOURCE_ID),
                    "source_version": "2023",
                    "parser_version": "science-v1",
                    "retrieved_at": "2026-08-07T20:00:00+00:00",
                    "resolved_document_url": "https://www.alabamaachieves.org/files/science.pdf",
                    "source_sha256": "a" * 64,
                    "normalized_sha256": "b" * 64,
                    "provenance": {"parser_status": "parsed"},
                }
            ]
        if resource == "standard_snapshot_courses":
            return [{"course_id": str(uuid4())}, {"course_id": str(uuid4())}]
        if resource == "standard_entries":
            return [{"id": str(uuid4())}, {"id": str(uuid4())}, {"id": str(uuid4())}]
        if resource == "rpc/approve_standard_snapshot":
            return str(SNAPSHOT_ID)
        if resource == "standard_catalog_discovery_runs":
            return [
                {
                    "id": str(RUN_ID),
                    "checked_at": "2026-08-07T20:00:00+00:00",
                    "check_month": "2026-08-01",
                    "trigger_kind": "manual",
                    "status": "completed",
                    "catalog_sha256": "c" * 64,
                    "discovered_source_count": 20,
                    "unchanged_count": 17,
                    "changed_count": 1,
                    "new_count": 2,
                    "missing_count": 0,
                    "error_summary": None,
                }
            ]
        if resource == "standard_catalog_discovery_items":
            return [
                {
                    "id": str(ITEM_ID),
                    "source_key": "alabama_academic_science",
                    "result_state": "changed",
                    "family": "alabama_academic",
                    "category_name": "Science",
                    "authority": "Alabama State Department of Education",
                    "observed_title": "2023 Alabama Course of Study: Science",
                    "observed_edition": "2023",
                    "observed_document_url": "https://www.alabamaachieves.org/files/science.pdf",
                    "previous_title": "Prior Science",
                    "previous_edition": "2015",
                    "previous_document_url": "https://www.alabamaachieves.org/files/science-old.pdf",
                }
            ]
        return []


def _identity() -> AuthenticatedTeacher:
    return AuthenticatedTeacher(
        subject=str(PLATFORM_ADMIN_ID),
        email="owner@example.test",
        display_name="Synthetic Platform Owner",
        school_id=str(SCHOOL_ID),
        roles=frozenset({"platform_admin", "teacher"}),
    )


def _install(monkeypatch, fake: FakeClient) -> None:
    monkeypatch.setattr(standards_admin_api, "_client", lambda identity, settings: fake)
    app.dependency_overrides[require_platform_admin] = _identity


def test_standards_admin_routes_require_authentication() -> None:
    response = client.get("/api/v1/standards-admin/sources")
    assert response.status_code == 404 or response.status_code == 401


def test_platform_admin_source_and_pending_snapshot_reads(monkeypatch) -> None:
    fake = FakeClient()
    _install(monkeypatch, fake)
    try:
        sources = standards_admin_api.list_admin_sources(
            _identity(),
            standards_admin_api.get_settings(),
        )
        pending = standards_admin_api.list_pending_snapshots(
            _identity(),
            standards_admin_api.get_settings(),
        )
    finally:
        app.dependency_overrides.pop(require_platform_admin, None)

    assert sources[0].source_key == "alabama_academic_science"
    assert pending[0].source_key == "alabama_academic_science"
    assert pending[0].course_count == 2
    assert pending[0].standard_entry_count == 3
    assert pending[0].parser_status == "parsed"


def test_snapshot_approval_uses_only_governed_approval_rpc(monkeypatch) -> None:
    fake = FakeClient()
    _install(monkeypatch, fake)
    try:
        result = standards_admin_api.approve_snapshot(
            SNAPSHOT_ID,
            _identity(),
            standards_admin_api.get_settings(),
        )
    finally:
        app.dependency_overrides.pop(require_platform_admin, None)

    assert result.snapshot_id == SNAPSHOT_ID
    assert result.status == "approved"
    assert fake.calls[-1][1] == "rpc/approve_standard_snapshot"
    assert fake.calls[-1][3] == {"target_snapshot_id": str(SNAPSHOT_ID)}
    assert not any(
        call[0] in {"PATCH", "PUT", "DELETE"}
        and call[1] in {"standard_sources", "standard_snapshots"}
        for call in fake.calls
    )


def test_catalog_run_detail_exposes_new_changed_missing_evidence(monkeypatch) -> None:
    fake = FakeClient()
    _install(monkeypatch, fake)
    try:
        detail = standards_admin_api.get_catalog_run(
            RUN_ID,
            _identity(),
            standards_admin_api.get_settings(),
        )
    finally:
        app.dependency_overrides.pop(require_platform_admin, None)

    assert detail.run.changed_count == 1
    assert detail.run.new_count == 2
    assert detail.items[0].result_state == "changed"
    assert detail.items[0].category_name == "Science"
