from uuid import UUID

from app import standards_maintenance as maintenance
from app.standards_ingest import (
    ExtractedDocument,
    FetchedSource,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
)
from app.standards_sources import ResolvedStandardsSource

SOURCE_ID = UUID("11111111-1111-1111-1111-111111111111")
SNAPSHOT_ID = UUID("22222222-2222-2222-2222-222222222222")


def _source() -> maintenance.StandardSourceRecord:
    return maintenance.StandardSourceRecord(
        id=SOURCE_ID,
        source_key="alabama_academic_english_language_arts",
        landing_url="https://www.alabamaachieves.org/content-areas-specialty/english-language-arts/",
        document_url="https://www.alabamaachieves.org/ela.pdf",
        document_format="pdf",
        resolver_key="alabama_ela_current",
        parser_key="alabama_ela_2021",
        source_kind="course_of_study",
        provides_standard_entries=True,
        approved_snapshot_id=None,
    )


def _resolved() -> ResolvedStandardsSource:
    return ResolvedStandardsSource(
        landing_url=_source().landing_url,
        document_url=_source().document_url,
        anchor_text="2021 Alabama Course of Study: English Language Arts",
        observed_version="2021",
    )


def _fetched() -> FetchedSource:
    return FetchedSource(
        requested_url=_source().document_url,
        resolved_url=_source().document_url,
        document_format="pdf",
        content=b"%PDF-test",
        source_sha256="a" * 64,
    )


def _parsed() -> ParsedStandardsDocument:
    return ParsedStandardsDocument(
        parser_key="alabama_ela_2021",
        parser_version="gate-e-alabama-ela-2021-v2",
        normalized_sha256="b" * 64,
        courses=(
            ParsedCourse(
                course_key="english_10",
                display_name="English 10",
                source_course_code="GRADE 10",
                grade_band="10",
                standards=(ParsedStandard(code="ELA10.1", text="Authoritative text"),),
            ),
        ),
    )


def test_landing_resolved_source_uses_governed_parser_dispatch(monkeypatch) -> None:
    calls: list[str] = []
    persisted: list[UUID] = []

    monkeypatch.setattr(maintenance, "_load_source", lambda client, source_key: _source())
    monkeypatch.setattr(maintenance, "_load_snapshot", lambda client, snapshot_id: None)
    monkeypatch.setattr(
        maintenance,
        "resolve_authoritative_document",
        lambda resolver_key, landing_url: _resolved(),
    )
    monkeypatch.setattr(maintenance, "fetch_source", lambda url, document_format: _fetched())
    monkeypatch.setattr(
        maintenance,
        "extract_document",
        lambda fetched: ExtractedDocument(lines=("test",), normalized_sha256="b" * 64),
    )

    def parse(parser_key, extracted):
        calls.append(parser_key)
        return _parsed()

    monkeypatch.setattr(maintenance, "parse_governed_standards_document", parse)
    monkeypatch.setattr(
        maintenance,
        "_stage_snapshot",
        lambda *args, **kwargs: SNAPSHOT_ID,
    )
    monkeypatch.setattr(
        maintenance,
        "_persist_parsed_standards",
        lambda client, source, snapshot_id, parsed: persisted.append(snapshot_id),
    )

    result = maintenance.stage_authoritative_source(object(), _source().source_key)

    assert calls == ["alabama_ela_2021"]
    assert persisted == [SNAPSHOT_ID]
    assert result.parser_succeeded is True
    assert result.candidate_snapshot_id == SNAPSHOT_ID


class RefreshClient:
    def __init__(self) -> None:
        self.patch_payload = None

    def request(self, method, resource, *, params=None, payload=None, prefer=None):
        if method == "GET" and resource == "standard_snapshots":
            return [
                {
                    "id": str(SNAPSHOT_ID),
                    "source_sha256": "a" * 64,
                    "normalized_sha256": "old",
                    "status": "pending",
                }
            ]
        if method == "PATCH" and resource == "standard_snapshots":
            assert params == {"id": f"eq.{SNAPSHOT_ID}"}
            assert prefer == "return=minimal"
            self.patch_payload = payload
            return None
        raise AssertionError(f"unexpected request: {method} {resource}")


def test_existing_pending_snapshot_refreshes_parser_metadata() -> None:
    client = RefreshClient()

    snapshot_id = maintenance._stage_snapshot(
        client,
        source=_source(),
        resolved=_resolved(),
        fetched=_fetched(),
        normalized_sha256="b" * 64,
        parser_key="alabama_ela_2021",
        parser_version="gate-e-alabama-ela-2021-v2",
        parser_succeeded=True,
        parser_error=None,
    )

    assert snapshot_id == SNAPSHOT_ID
    assert client.patch_payload is not None
    assert client.patch_payload["parser_version"] == "gate-e-alabama-ela-2021-v2"
    assert client.patch_payload["normalized_sha256"] == "b" * 64
    assert client.patch_payload["provenance"]["parser_key"] == "alabama_ela_2021"
    assert client.patch_payload["provenance"]["parser_status"] == "parsed"
