from datetime import date
from uuid import uuid4

import httpx
import pytest

from app import standards_catalog_fetch, standards_monthly_run
from app.standards_catalog_discovery import StandardsCatalogDiscoveryError
from app.standards_catalog_reconcile import CatalogReconcileResult
from app.standards_governed_sources import list_governed_source_keys
from app.standards_maintenance import MaintenanceResult


class FakeRestClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str, object]] = []

    def request(self, method: str, resource: str, *, params=None, payload=None, prefer=None):
        self.calls.append((method, resource, params))
        return self.payload


def test_governed_source_list_is_dynamic_and_approved_only() -> None:
    client = FakeRestClient(
        [
            {"source_key": "alabama_academic_science"},
            {"source_key": "army_jrotc_curriculum"},
        ]
    )

    assert list_governed_source_keys(client) == (
        "alabama_academic_science",
        "army_jrotc_curriculum",
    )
    params = client.calls[0][2]
    assert params["is_active"] == "eq.true"
    assert params["discovery_status"] == "eq.approved"
    assert "source_key" in params["select"]


class FakeHttpResponse:
    def __init__(self, url: str, text: str, *, final_url: str | None = None) -> None:
        self.url = httpx.URL(final_url or url)
        self.text = text
        self.content = text.encode("utf-8")

    def raise_for_status(self) -> None:
        return None


class FakeHttpClient:
    def __init__(self, pages: dict[str, FakeHttpResponse]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str) -> FakeHttpResponse:
        self.requested.append(url)
        return self.pages[url]


def test_catalog_fetch_reads_academic_cte_cos_and_program_roots(monkeypatch) -> None:
    pages = {
        standards_catalog_fetch.ACADEMIC_CATALOG_URL: FakeHttpResponse(
            standards_catalog_fetch.ACADEMIC_CATALOG_URL,
            """
            <h3>Science</h3><h4>Title</h4>
            <a href="/files/science.pdf">2024 Alabama Course of Study: Science</a>
            """,
        ),
        standards_catalog_fetch.CTE_COS_CATALOG_URL: FakeHttpResponse(
            standards_catalog_fetch.CTE_COS_CATALOG_URL,
            """
            <h3>Finance</h3><h4>Title</h4>
            <a href="/files/finance.pdf">2021 Finance Course of Study</a>
            """,
        ),
        standards_catalog_fetch.CTE_PROGRAM_CATALOG_URL: FakeHttpResponse(
            standards_catalog_fetch.CTE_PROGRAM_CATALOG_URL,
            """
            <h3>Program Guides</h3><h4>Government &amp; Public Administration</h4>
            <a href="/files/gpa.pdf">Government Program Guide 2025-2026</a>
            """,
        ),
    }
    fake = FakeHttpClient(pages)
    monkeypatch.setattr(
        standards_catalog_fetch.httpx,
        "Client",
        lambda **kwargs: fake,
    )

    sources = standards_catalog_fetch.fetch_current_alabama_catalog()

    assert set(fake.requested) == set(pages)
    assert {source.source_key for source in sources} == {
        "alabama_academic_science",
        "alabama_cte_cos_finance",
        "alabama_cte_program_government_public_administration",
    }


def test_catalog_fetch_rejects_redirect_outside_alabama_allowlist(monkeypatch) -> None:
    pages = {
        standards_catalog_fetch.ACADEMIC_CATALOG_URL: FakeHttpResponse(
            standards_catalog_fetch.ACADEMIC_CATALOG_URL,
            "<html></html>",
            final_url="https://example.com/catalog",
        )
    }
    fake = FakeHttpClient(pages)
    monkeypatch.setattr(
        standards_catalog_fetch.httpx,
        "Client",
        lambda **kwargs: fake,
    )

    with pytest.raises(StandardsCatalogDiscoveryError):
        standards_catalog_fetch.fetch_current_alabama_catalog()


def _maintenance(source_key: str, status: str = "unchanged") -> MaintenanceResult:
    return MaintenanceResult(
        source_key=source_key,
        status=status,
        approved_snapshot_id=uuid4(),
        candidate_snapshot_id=None,
        observed_source_sha256="a" * 64,
        normalized_sha256="b" * 64,
        parser_succeeded=True,
        detail="Synthetic maintenance result",
    )


def test_monthly_run_uses_dynamic_governed_sources(monkeypatch) -> None:
    checked: list[str] = []
    monkeypatch.setattr(
        standards_monthly_run,
        "fetch_current_alabama_catalog",
        lambda: (),
    )
    monkeypatch.setattr(
        standards_monthly_run,
        "reconcile_and_record_catalog",
        lambda client, discovered, check_month, trigger_kind: CatalogReconcileResult(
            run_id=uuid4(),
            catalog_sha256="c" * 64,
            items=(),
        ),
    )
    monkeypatch.setattr(
        standards_monthly_run,
        "list_governed_source_keys",
        lambda client: ("source_one", "source_two"),
    )

    def stage(client, source_key, *, check_month):
        checked.append(source_key)
        return _maintenance(source_key)

    monkeypatch.setattr(standards_monthly_run, "stage_authoritative_source", stage)

    result = standards_monthly_run.run_monthly_standards_validation(
        object(),
        check_date=date(2026, 8, 3),
    )

    assert checked == ["source_one", "source_two"]
    assert not result.requires_review
    assert not result.has_unavailable_error


def test_catalog_outage_is_recorded_but_existing_sources_are_still_checked(monkeypatch) -> None:
    checked: list[str] = []
    error_run_id = uuid4()

    def fail_fetch():
        raise StandardsCatalogDiscoveryError("Synthetic catalog outage")

    monkeypatch.setattr(standards_monthly_run, "fetch_current_alabama_catalog", fail_fetch)
    monkeypatch.setattr(
        standards_monthly_run,
        "record_catalog_discovery_error",
        lambda client, **kwargs: error_run_id,
    )
    monkeypatch.setattr(
        standards_monthly_run,
        "list_governed_source_keys",
        lambda client: ("existing_source",),
    )

    def stage(client, source_key, *, check_month):
        checked.append(source_key)
        return _maintenance(source_key)

    monkeypatch.setattr(standards_monthly_run, "stage_authoritative_source", stage)

    result = standards_monthly_run.run_monthly_standards_validation(
        object(),
        check_date=date(2026, 8, 3),
    )

    assert checked == ["existing_source"]
    assert result.catalog_error_run_id == error_run_id
    assert result.catalog_error == "Synthetic catalog outage"
    assert result.has_unavailable_error
