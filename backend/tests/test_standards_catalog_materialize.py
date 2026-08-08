from uuid import uuid4

import pytest

from app import standards_catalog_materialize as materialize
from app.standards_catalog_discovery import DiscoveredStandardsSource
from app.standards_catalog_materialize import materialize_discovered_source
from app.standards_course_catalog import (
    ParsedCourseCatalogDocument,
    ParsedCourseListing,
)
from app.standards_ingest import (
    ExtractedDocument,
    FetchedSource,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
)

SOURCE_ID = uuid4()
SNAPSHOT_ID = uuid4()
COURSE_ID = uuid4()


def _source(
    source_key: str,
    family: str,
    *,
    source_kind: str = "course_of_study",
) -> DiscoveredStandardsSource:
    return DiscoveredStandardsSource(
        source_key=source_key,
        family=family,
        category_key="science" if family == "alabama_academic" else "finance",
        category_name="Science" if family == "alabama_academic" else "Finance",
        category_type="academic_subject" if family == "alabama_academic" else "career_cluster",
        authority="Alabama State Department of Education",
        title="Synthetic authoritative source",
        edition="2026",
        landing_url="https://www.alabamaachieves.org/acad-stand/",
        document_url="https://www.alabamaachieves.org/files/synthetic.pdf",
        document_format="pdf",
        parser_key_hint="synthetic",
        source_kind=source_kind,
    )


class FakeClient:
    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.calls: list[tuple[str, str, object, object, object]] = []

    def request(self, method, resource, *, params=None, payload=None, prefer=None):
        self.calls.append((method, resource, params, payload, prefer))
        if method == "GET" and resource == "standard_sources":
            return [self.existing] if self.existing is not None else []
        if method in {"POST", "PATCH"} and resource == "standard_sources":
            return [{"id": str(SOURCE_ID)}]
        if method == "GET" and resource == "standard_snapshots":
            return []
        if method == "POST" and resource == "standard_snapshots":
            return [{"id": str(SNAPSHOT_ID)}]
        if method == "POST" and resource == "standard_courses":
            return [{"id": str(COURSE_ID)}]
        if resource in {"standard_entries", "standard_snapshot_courses"}:
            return None
        raise AssertionError(f"Unexpected request: {method} {resource}")


def test_parser_pending_source_stages_metadata_only(monkeypatch) -> None:
    client = FakeClient()
    source = _source("alabama_academic_future_subject", "alabama_academic")
    monkeypatch.setattr(
        materialize,
        "fetch_source",
        lambda *args, **kwargs: pytest.fail("parser-pending source must not be fetched"),
    )

    result = materialize_discovered_source(client, source)

    assert result.status == "parser_pending"
    assert result.source_id == SOURCE_ID
    source_call = next(
        call
        for call in client.calls
        if call[1] == "standard_sources" and call[0] == "POST"
    )
    assert source_call[3]["discovery_status"] == "pending"
    assert source_call[3]["parser_key"] == "alabama_academic_parser_pending"
    assert not any(
        call[1] == "standard_snapshots" and call[0] == "POST"
        for call in client.calls
    )


def test_approved_source_descriptor_is_never_patched_by_catalog_materialization() -> None:
    source = _source("alabama_academic_science", "alabama_academic")
    existing = {
        "id": str(SOURCE_ID),
        "source_key": source.source_key,
        "family": source.family,
        "authority": source.authority,
        "title": "Older approved source title",
        "edition": "2023",
        "landing_url": source.landing_url,
        "document_url": "https://www.alabamaachieves.org/files/science-2023.pdf",
        "document_format": "pdf",
        "parser_key": "alabama_science_2023",
        "source_kind": "course_of_study",
        "provides_standard_entries": True,
        "catalog_category_key": source.category_key,
        "catalog_category_name": source.category_name,
        "catalog_category_type": source.category_type,
        "discovery_status": "approved",
        "approved_snapshot_id": str(uuid4()),
    }
    client = FakeClient(existing=existing)

    result = materialize_discovered_source(client, source)

    assert result.status == "approved_source_change_requires_review"
    assert not any(
        call[0] in {"PATCH", "POST"}
        and call[1] == "standard_sources"
        for call in client.calls
    )


def test_ready_academic_source_stages_parsed_candidate_without_approval(monkeypatch) -> None:
    client = FakeClient()
    source = _source("alabama_academic_science", "alabama_academic")
    fetched = FetchedSource(
        requested_url=source.document_url,
        resolved_url=source.document_url,
        document_format="pdf",
        content=b"%PDF synthetic",
        source_sha256="a" * 64,
    )
    extracted = ExtractedDocument(lines=("synthetic",), normalized_sha256="b" * 64)
    parsed = ParsedStandardsDocument(
        parser_key="alabama_science_2023",
        parser_version="synthetic-parser-v1",
        normalized_sha256=extracted.normalized_sha256,
        courses=(
            ParsedCourse(
                course_key="biology",
                display_name="Biology",
                source_course_code=None,
                grade_band="9-12",
                standards=(ParsedStandard(code="1", text="Synthetic standard"),),
            ),
        ),
    )
    monkeypatch.setattr(materialize, "fetch_source", lambda *args, **kwargs: fetched)
    monkeypatch.setattr(materialize, "extract_document", lambda value: extracted)
    monkeypatch.setattr(
        materialize,
        "parse_governed_standards_document",
        lambda parser_key, value: parsed,
    )

    result = materialize_discovered_source(client, source)

    assert result.status == "candidate_staged"
    assert result.candidate_snapshot_id == SNAPSHOT_ID
    assert not any(call[1] == "rpc/approve_standard_snapshot" for call in client.calls)
    manifest_call = next(
        call
        for call in client.calls
        if call[1] == "standard_snapshot_courses" and call[0] == "POST"
    )
    assert manifest_call[3]["display_name"] == "Biology"
    entry_call = next(
        call
        for call in client.calls
        if call[1] == "standard_entries" and call[0] == "POST"
    )
    assert entry_call[3][0]["code"] == "1"


def test_program_guide_candidate_contains_course_manifest_but_no_standard_entries(
    monkeypatch,
) -> None:
    client = FakeClient()
    source = _source(
        "alabama_cte_program_finance",
        "alabama_cte_program",
        source_kind="program_guide",
    )
    fetched = FetchedSource(
        requested_url=source.document_url,
        resolved_url=source.document_url,
        document_format="pdf",
        content=b"%PDF synthetic program guide",
        source_sha256="c" * 64,
    )
    extracted = ExtractedDocument(lines=("course listing",), normalized_sha256="d" * 64)
    parsed = ParsedCourseCatalogDocument(
        parser_key="alabama_cte_program_generic",
        parser_version="synthetic-catalog-v1",
        normalized_sha256=extracted.normalized_sha256,
        courses=(
            ParsedCourseListing(
                course_key="financial_services",
                display_name="Financial Services",
                source_course_code="12001G1001",
                grade_band="9-12",
            ),
        ),
    )
    monkeypatch.setattr(materialize, "fetch_source", lambda *args, **kwargs: fetched)
    monkeypatch.setattr(materialize, "extract_document", lambda value: extracted)
    monkeypatch.setattr(
        materialize,
        "parse_course_catalog_document",
        lambda parser_key, value: parsed,
    )

    result = materialize_discovered_source(client, source)

    assert result.status == "candidate_staged"
    assert any(call[1] == "standard_snapshot_courses" for call in client.calls)
    assert not any(
        call[1] == "standard_entries" and call[0] == "POST"
        for call in client.calls
    )
