from datetime import date
from hashlib import sha256
from uuid import uuid4

import pytest

import app.standards_maintenance as maintenance
from app.standards_ingest import (
    ExtractedDocument,
    FetchedSource,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)
from app.standards_maintenance import (
    SnapshotRecord,
    StandardsMaintenanceError,
    StandardSourceRecord,
    stage_authoritative_source,
)
from app.standards_sources import ResolvedStandardsSource, StandardsSourceResolutionError

SOURCE_ID = uuid4()
APPROVED_ID = uuid4()
CANDIDATE_ID = uuid4()
SOURCE = StandardSourceRecord(
    id=SOURCE_ID,
    source_key="army_jrotc_v12",
    landing_url="https://usarmyjrotc.army.mil/jsocc-course-documents/",
    document_url=(
        "https://usarmyjrotc.army.mil/wp-content/uploads/2025/07/"
        "JROTC-Curriculum-Guide-25JUN25-4.docx"
    ),
    document_format="docx",
    resolver_key="army_jrotc_current",
    parser_key="army_jrotc_v12",
    approved_snapshot_id=APPROVED_ID,
)
APPROVED = SnapshotRecord(
    id=APPROVED_ID,
    source_sha256="a" * 64,
    normalized_sha256="b" * 64,
    status="approved",
)
RESOLVED = ResolvedStandardsSource(
    landing_url=SOURCE.landing_url,
    document_url=SOURCE.document_url,
    anchor_text="JROTC Curriculum Guide v12",
    observed_version="v12",
)


class DummyClient:
    pass


def _fetched(raw: bytes) -> FetchedSource:
    return FetchedSource(
        requested_url=SOURCE.document_url,
        resolved_url=SOURCE.document_url,
        document_format="docx",
        content=raw,
        source_sha256=sha256(raw).hexdigest(),
    )


def _install_common(monkeypatch) -> None:
    monkeypatch.setattr(maintenance, "_load_source", lambda client, source_key: SOURCE)
    monkeypatch.setattr(maintenance, "_load_snapshot", lambda client, snapshot_id: APPROVED)
    monkeypatch.setattr(
        maintenance,
        "resolve_authoritative_document",
        lambda resolver_key, landing_url: RESOLVED,
    )
    monkeypatch.setattr(
        maintenance,
        "_update_resolved_document_url",
        lambda client, source, resolved: None,
    )


def test_unavailable_source_records_error_without_replacing_approved_snapshot(monkeypatch) -> None:
    _install_common(monkeypatch)
    recorded: list[dict[str, object]] = []

    def fail_resolve(resolver_key, landing_url):
        raise StandardsSourceResolutionError("publisher unavailable")

    monkeypatch.setattr(maintenance, "resolve_authoritative_document", fail_resolve)
    monkeypatch.setattr(
        maintenance,
        "_record_check",
        lambda client, **kwargs: recorded.append(kwargs),
    )

    result = stage_authoritative_source(
        DummyClient(),
        SOURCE.source_key,
        check_month=date(2026, 8, 7),
    )

    assert result.status == "unavailable_error"
    assert result.approved_snapshot_id == APPROVED_ID
    assert result.candidate_snapshot_id is None
    assert recorded[0]["status"] == "unavailable_error"
    assert recorded[0]["approved"] == APPROVED


def test_same_raw_fingerprint_is_unchanged_and_does_not_stage_candidate(monkeypatch) -> None:
    _install_common(monkeypatch)
    fetched = FetchedSource(
        requested_url=SOURCE.document_url,
        resolved_url=SOURCE.document_url,
        document_format="docx",
        content=b"same source",
        source_sha256=APPROVED.source_sha256,
    )
    recorded: list[object] = []
    monkeypatch.setattr(maintenance, "fetch_source", lambda url, document_format: fetched)
    monkeypatch.setattr(
        maintenance,
        "_record_result_if_requested",
        lambda *args, **kwargs: recorded.append(args[4]),
    )
    monkeypatch.setattr(
        maintenance,
        "_stage_snapshot",
        lambda *args, **kwargs: pytest.fail("unchanged source must not stage a candidate"),
    )

    result = stage_authoritative_source(
        DummyClient(),
        SOURCE.source_key,
        check_month=date(2026, 8, 1),
    )

    assert result.status == "unchanged"
    assert result.candidate_snapshot_id is None
    assert recorded[0].status == "unchanged"


def test_raw_file_change_with_same_normalized_text_is_unchanged(monkeypatch) -> None:
    _install_common(monkeypatch)
    fetched = _fetched(b"new archive packaging")
    monkeypatch.setattr(maintenance, "fetch_source", lambda url, document_format: fetched)
    monkeypatch.setattr(
        maintenance,
        "extract_document",
        lambda source: ExtractedDocument(
            lines=("same normalized standards",),
            normalized_sha256=APPROVED.normalized_sha256,
        ),
    )
    monkeypatch.setattr(
        maintenance,
        "parse_document",
        lambda parser_key, extracted: pytest.fail("same normalized content must not be reparsed"),
    )
    monkeypatch.setattr(
        maintenance,
        "_stage_snapshot",
        lambda *args, **kwargs: pytest.fail("same normalized content must not stage a candidate"),
    )
    monkeypatch.setattr(
        maintenance,
        "_record_result_if_requested",
        lambda *args, **kwargs: None,
    )

    result = stage_authoritative_source(DummyClient(), SOURCE.source_key)

    assert result.status == "unchanged"
    assert result.observed_source_sha256 == fetched.source_sha256
    assert "normalized authoritative content is unchanged" in result.detail


def test_changed_parsed_content_stages_candidate_and_persists_entries(monkeypatch) -> None:
    _install_common(monkeypatch)
    fetched = _fetched(b"meaningfully changed source")
    extracted = ExtractedDocument(
        lines=("U1C1L1: Updated lesson",),
        normalized_sha256="c" * 64,
    )
    parsed = ParsedStandardsDocument(
        parser_key="army_jrotc_v12",
        parser_version="gate-e-standards-v1",
        normalized_sha256=extracted.normalized_sha256,
        courses=(
            ParsedCourse(
                course_key="army_jrotc_let_1",
                display_name="Army JROTC LET 1",
                source_course_code="LET 1",
                grade_band="9-12",
                standards=(ParsedStandard(code="U1C1L1", text="Updated lesson"),),
            ),
        ),
    )
    persisted: list[tuple[object, ...]] = []
    monkeypatch.setattr(maintenance, "fetch_source", lambda url, document_format: fetched)
    monkeypatch.setattr(maintenance, "extract_document", lambda source: extracted)
    monkeypatch.setattr(maintenance, "parse_document", lambda parser_key, value: parsed)
    monkeypatch.setattr(
        maintenance,
        "_stage_snapshot",
        lambda *args, **kwargs: CANDIDATE_ID,
    )
    monkeypatch.setattr(
        maintenance,
        "_persist_parsed_courses",
        lambda *args: persisted.append(args),
    )
    monkeypatch.setattr(
        maintenance,
        "_record_result_if_requested",
        lambda *args, **kwargs: None,
    )

    result = stage_authoritative_source(DummyClient(), SOURCE.source_key)

    assert result.status == "changed"
    assert result.candidate_snapshot_id == CANDIDATE_ID
    assert result.parser_succeeded is True
    assert persisted and persisted[0][2] == CANDIDATE_ID


def test_changed_unparseable_source_stages_nonapprovable_candidate(monkeypatch) -> None:
    _install_common(monkeypatch)
    fetched = _fetched(b"publisher changed structure")
    extracted = ExtractedDocument(
        lines=("unknown structure",),
        normalized_sha256="d" * 64,
    )
    stage_calls: list[dict[str, object]] = []
    monkeypatch.setattr(maintenance, "fetch_source", lambda url, document_format: fetched)
    monkeypatch.setattr(maintenance, "extract_document", lambda source: extracted)

    def fail_parse(parser_key, value):
        raise StandardsIngestError("expected course structure disappeared")

    monkeypatch.setattr(maintenance, "parse_document", fail_parse)

    def stage(*args, **kwargs):
        stage_calls.append(kwargs)
        return CANDIDATE_ID

    monkeypatch.setattr(maintenance, "_stage_snapshot", stage)
    monkeypatch.setattr(
        maintenance,
        "_persist_parsed_courses",
        lambda *args: pytest.fail("unparseable candidate must not persist standards entries"),
    )
    monkeypatch.setattr(
        maintenance,
        "_record_result_if_requested",
        lambda *args, **kwargs: None,
    )

    result = stage_authoritative_source(DummyClient(), SOURCE.source_key)

    assert result.status == "changed"
    assert result.candidate_snapshot_id == CANDIDATE_ID
    assert result.parser_succeeded is False
    assert stage_calls[0]["parser_succeeded"] is False
    assert "expected course structure disappeared" in stage_calls[0]["parser_error"]


def test_service_role_client_refuses_missing_privileged_configuration() -> None:
    class MissingSettings:
        supabase_url = None
        supabase_service_role_key = None

    with pytest.raises(StandardsMaintenanceError, match="database access is not configured"):
        maintenance.service_role_client(MissingSettings())
