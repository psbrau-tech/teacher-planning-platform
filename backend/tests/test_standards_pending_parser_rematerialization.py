from datetime import date
from uuid import UUID, uuid4

from app import standards_pending_parser_rematerialization as rematerialization
from app.standards_ingest import (
    ExtractedDocument,
    FetchedSource,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
)
from app.standards_maintenance import StandardSourceRecord

SOURCE_ID = uuid4()
BASELINE_ID = uuid4()
CANDIDATE_ID = uuid4()
SOURCE_SHA = "a" * 64
NORMALIZED_SHA = "b" * 64


class FakeClient:
    def __init__(self, *, include_current: bool = False) -> None:
        self.include_current = include_current
        self.calls: list[tuple[str, str, object, object]] = []

    def request(self, method, resource, *, params=None, payload=None, prefer=None):
        self.calls.append((method, resource, params, payload))
        if method == "GET" and resource == "standard_snapshots":
            rows = [
                {
                    "id": str(BASELINE_ID),
                    "status": "pending",
                    "parser_version": "gate-e-alabama-aas-math-2019-v1",
                    "normalized_sha256": NORMALIZED_SHA,
                    "source_version": "2019",
                    "retrieved_at": "2026-08-10T23:51:56+00:00",
                }
            ]
            if self.include_current:
                rows.append(
                    {
                        "id": str(CANDIDATE_ID),
                        "status": "pending",
                        "parser_version": "gate-e-alabama-aas-math-2019-v2",
                        "normalized_sha256": NORMALIZED_SHA,
                        "source_version": "2019",
                        "retrieved_at": "2026-08-11T01:00:00+00:00",
                    }
                )
            return rows
        if method == "POST" and resource == "standard_snapshots":
            return [{"id": str(CANDIDATE_ID)}]
        return []


def _source(*, approved_snapshot_id: UUID | None = None) -> StandardSourceRecord:
    return StandardSourceRecord(
        id=SOURCE_ID,
        source_key="alabama_alternate_mathematics",
        landing_url="https://www.alabamaachieves.org/special-education/subject-resources/",
        document_url="https://www.alabamaachieves.org/files/aas-math.pdf",
        document_format="pdf",
        resolver_key="catalog_discovered_direct",
        parser_key="alabama_aas_math_2019",
        source_kind="alternate_achievement_standards",
        provides_standard_entries=True,
        approved_snapshot_id=approved_snapshot_id,
    )


def _parsed() -> ParsedStandardsDocument:
    return ParsedStandardsDocument(
        parser_key="alabama_aas_math_2019",
        parser_version="gate-e-alabama-aas-math-2019-v2",
        normalized_sha256=NORMALIZED_SHA,
        courses=(
            ParsedCourse(
                course_key="grade_9",
                display_name="Grade 9 Geometry with Data Analysis",
                source_course_code="Grade 9 Geometry with Data Analysis",
                grade_band="9",
                standards=(
                    ParsedStandard(
                        code="M.G.AAS.9.1",
                        text="Synthetic alternate math standard.",
                    ),
                ),
            ),
        ),
    )


def _install(monkeypatch, persisted: list[UUID]) -> None:
    monkeypatch.setattr(rematerialization, "_load_source", lambda client, source_key: _source())
    monkeypatch.setattr(
        rematerialization,
        "fetch_source",
        lambda url, document_format: FetchedSource(
            requested_url=url,
            resolved_url=url,
            document_format=document_format,
            content=b"%PDF synthetic",
            source_sha256=SOURCE_SHA,
        ),
    )
    monkeypatch.setattr(
        rematerialization,
        "extract_document",
        lambda fetched: ExtractedDocument(
            lines=("synthetic",),
            normalized_sha256=NORMALIZED_SHA,
            source_content=fetched.content,
            document_format=fetched.document_format,
        ),
    )
    monkeypatch.setattr(rematerialization, "parse_document", lambda parser_key, extracted: _parsed())
    monkeypatch.setattr(
        rematerialization,
        "_persist_parsed_standards",
        lambda client, source, snapshot_id, parsed: persisted.append(snapshot_id),
    )


def test_pending_parser_upgrade_stages_distinct_immutable_candidate(monkeypatch) -> None:
    persisted: list[UUID] = []
    _install(monkeypatch, persisted)
    client = FakeClient()

    result = rematerialization.stage_pending_parser_rematerialization_if_needed(
        client,
        "alabama_alternate_mathematics",
        check_date=date(2026, 8, 10),
    )

    assert result is not None
    assert result.candidate_snapshot_id == CANDIDATE_ID
    assert result.approved_snapshot_id is None
    assert persisted == [CANDIDATE_ID]

    snapshot_posts = [
        call for call in client.calls if call[0] == "POST" and call[1] == "standard_snapshots"
    ]
    assert len(snapshot_posts) == 1
    payload = snapshot_posts[0][3]
    assert payload["parser_version"] == "gate-e-alabama-aas-math-2019-v2"
    assert payload["source_sha256"] == SOURCE_SHA
    assert payload["provenance"]["rematerialized_from_snapshot_id"] == str(BASELINE_ID)
    assert payload["provenance"]["rematerialization_reason"] == (
        "reviewed_parser_version_change_before_initial_approval"
    )
    assert not any(
        call[0] == "PATCH"
        and call[1] == "standard_snapshots"
        and call[2] == {"id": f"eq.{BASELINE_ID}"}
        for call in client.calls
    )


def test_pending_parser_upgrade_refreshes_only_same_version_candidate(monkeypatch) -> None:
    persisted: list[UUID] = []
    _install(monkeypatch, persisted)
    client = FakeClient(include_current=True)

    result = rematerialization.stage_pending_parser_rematerialization_if_needed(
        client,
        "alabama_alternate_mathematics",
        check_date=date(2026, 8, 10),
    )

    assert result is not None
    assert result.candidate_snapshot_id == CANDIDATE_ID
    assert persisted == [CANDIDATE_ID]
    assert not any(
        call[0] == "POST" and call[1] == "standard_snapshots" for call in client.calls
    )
    assert any(
        call[0] == "PATCH"
        and call[1] == "standard_snapshots"
        and call[2] == {"id": f"eq.{CANDIDATE_ID}"}
        for call in client.calls
    )
    assert not any(
        call[0] == "PATCH"
        and call[1] == "standard_snapshots"
        and call[2] == {"id": f"eq.{BASELINE_ID}"}
        for call in client.calls
    )
