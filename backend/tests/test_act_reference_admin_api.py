from uuid import uuid4

from fastapi.testclient import TestClient

from app import act_reference_admin_api
from app.auth import AuthenticatedTeacher, require_platform_admin
from app.main import app

client = TestClient(app)
PLATFORM_ADMIN_ID = uuid4()
SCHOOL_ID = uuid4()
SOURCE_ID = uuid4()
SNAPSHOT_ID = uuid4()


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object, object]] = []

    def request(self, method, resource, *, params=None, payload=None, prefer=None):
        self.calls.append((method, resource, params, payload))
        if resource == "act_reference_snapshots":
            return [
                {
                    "id": str(SNAPSHOT_ID),
                    "source_id": str(SOURCE_ID),
                    "retrieved_at": "2026-08-08T20:00:00+00:00",
                    "parser_version": "gate-e-act-readiness-benchmarks-v1",
                    "source_sha256": "a" * 64,
                    "normalized_sha256": "b" * 64,
                    "status": "pending",
                }
            ]
        if resource == "act_reference_sources":
            return [
                {
                    "source_key": "act_readiness_benchmarks",
                    "title": "ACT College Readiness Benchmarks",
                    "source_type": "readiness_benchmark",
                    "document_url": "https://www.act.org/content/act/en/college-and-career-readiness/benchmarks.html",
                    "edition": "current public web edition",
                    "effective_date": None,
                }
            ]
        if resource == "act_reference_entries":
            return []
        if resource == "act_readiness_benchmarks":
            return [{"id": str(uuid4())} for _ in range(6)]
        if resource == "rpc/approve_act_reference_snapshot":
            return {
                "snapshot_id": str(SNAPSHOT_ID),
                "source_id": str(SOURCE_ID),
                "status": "approved",
                "changed": True,
            }
        raise AssertionError(f"unexpected request: {method} {resource}")


def _identity() -> AuthenticatedTeacher:
    return AuthenticatedTeacher(
        subject=str(PLATFORM_ADMIN_ID),
        email="owner@example.test",
        display_name="Synthetic Platform Owner",
        school_id=str(SCHOOL_ID),
        roles=frozenset({"platform_admin", "teacher"}),
    )


def _install(monkeypatch, fake: FakeClient) -> None:
    monkeypatch.setattr(act_reference_admin_api, "_client", lambda identity, settings: fake)
    app.dependency_overrides[require_platform_admin] = _identity


def test_act_reference_admin_route_requires_authentication() -> None:
    response = client.get("/api/v1/act-reference-admin/pending")
    assert response.status_code == 401


def test_pending_act_benchmark_snapshot_exposes_review_provenance_and_counts(monkeypatch) -> None:
    fake = FakeClient()
    _install(monkeypatch, fake)
    try:
        pending = act_reference_admin_api.list_pending_act_reference_snapshots(
            _identity(),
            act_reference_admin_api.get_settings(),
        )
    finally:
        app.dependency_overrides.pop(require_platform_admin, None)

    assert len(pending) == 1
    snapshot = pending[0]
    assert snapshot.source_key == "act_readiness_benchmarks"
    assert snapshot.source_type == "readiness_benchmark"
    assert snapshot.entry_count == 0
    assert snapshot.benchmark_count == 6
    assert snapshot.source_document_url.startswith("https://www.act.org/")
    assert snapshot.source_edition == "current public web edition"


def test_act_snapshot_approval_uses_only_governed_approval_rpc(monkeypatch) -> None:
    fake = FakeClient()
    _install(monkeypatch, fake)
    try:
        result = act_reference_admin_api.approve_act_reference_snapshot(
            SNAPSHOT_ID,
            _identity(),
            act_reference_admin_api.get_settings(),
        )
    finally:
        app.dependency_overrides.pop(require_platform_admin, None)

    assert result.snapshot_id == SNAPSHOT_ID
    assert result.status == "approved"
    assert fake.calls[-1][1] == "rpc/approve_act_reference_snapshot"
    assert fake.calls[-1][3] == {"target_snapshot_id": str(SNAPSHOT_ID)}
    assert not any(call[0] in {"PATCH", "PUT", "DELETE"} for call in fake.calls)
