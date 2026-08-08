from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast
from uuid import UUID

from .standards_catalog_discovery import DiscoveredStandardsSource
from .standards_course_catalog import (
    ParsedCourseCatalogDocument,
    parse_course_catalog_document,
)
from .standards_ingest import (
    ParsedStandardsDocument,
    StandardsIngestError,
    extract_document,
    fetch_source,
)
from .standards_parser_dispatch import parse_governed_standards_document
from .standards_source_registry import SourceIngestPlan, source_ingest_plan
from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]
MaterializeStatus = Literal[
    "parser_pending",
    "candidate_staged",
    "candidate_parse_failed",
    "approved_source_unchanged",
    "approved_source_change_requires_review",
]


class CatalogMaterializeError(RuntimeError):
    """Bounded failure while staging a discovered authoritative source."""


@dataclass(frozen=True, slots=True)
class CatalogMaterializeResult:
    source_key: str
    status: MaterializeStatus
    source_id: UUID
    candidate_snapshot_id: UUID | None
    parser_ready: bool
    parser_succeeded: bool
    detail: str


def materialize_discovered_source(
    client: SupabaseRestClient,
    discovered: DiscoveredStandardsSource,
) -> CatalogMaterializeResult:
    plan = source_ingest_plan(discovered)
    existing = _load_existing_source(client, discovered.source_key)

    if existing is not None and _optional_text(existing, "discovery_status") == "approved":
        source_id = _required_uuid(existing, "id")
        if _approved_descriptor_matches(existing, discovered):
            return CatalogMaterializeResult(
                source_key=discovered.source_key,
                status="approved_source_unchanged",
                source_id=source_id,
                candidate_snapshot_id=None,
                parser_ready=plan.parser_ready,
                parser_succeeded=True,
                detail="Approved source descriptor matches the current catalog discovery",
            )
        return CatalogMaterializeResult(
            source_key=discovered.source_key,
            status="approved_source_change_requires_review",
            source_id=source_id,
            candidate_snapshot_id=None,
            parser_ready=plan.parser_ready,
            parser_succeeded=False,
            detail=(
                "Approved source descriptor changed in catalog discovery; existing approved "
                "metadata was preserved pending governed review"
            ),
        )

    source_id = _upsert_pending_source(client, discovered, plan, existing)
    if not plan.parser_ready:
        return CatalogMaterializeResult(
            source_key=discovered.source_key,
            status="parser_pending",
            source_id=source_id,
            candidate_snapshot_id=None,
            parser_ready=False,
            parser_succeeded=False,
            detail=plan.readiness_detail,
        )

    fetched = fetch_source(discovered.document_url, discovered.document_format)
    extracted = extract_document(fetched)
    parsed_standards: ParsedStandardsDocument | None = None
    parsed_catalog: ParsedCourseCatalogDocument | None = None
    parse_error: str | None = None
    parser_version: str | None = None

    try:
        if plan.source_kind == "program_guide":
            parsed_catalog = parse_course_catalog_document(plan.parser_key, extracted)
            parser_version = parsed_catalog.parser_version
        elif plan.provides_standard_entries:
            parsed_standards = parse_governed_standards_document(plan.parser_key, extracted)
            parser_version = parsed_standards.parser_version
        else:
            raise StandardsIngestError(
                f"Unsupported catalog materialization role: {plan.source_kind}"
            )
    except StandardsIngestError as error:
        parse_error = str(error)

    snapshot_id = _stage_candidate_snapshot(
        client,
        source_id=source_id,
        discovered=discovered,
        fetched_source_sha256=fetched.source_sha256,
        resolved_document_url=fetched.resolved_url,
        normalized_sha256=extracted.normalized_sha256,
        parser_key=plan.parser_key,
        parser_version=parser_version,
        parser_succeeded=parsed_standards is not None or parsed_catalog is not None,
        parser_error=parse_error,
        plan=plan,
    )

    if parsed_standards is not None:
        _persist_standard_document(client, source_id, snapshot_id, parsed_standards)
    elif parsed_catalog is not None:
        _persist_course_catalog(client, source_id, snapshot_id, parsed_catalog)

    if parsed_standards is None and parsed_catalog is None:
        return CatalogMaterializeResult(
            source_key=discovered.source_key,
            status="candidate_parse_failed",
            source_id=source_id,
            candidate_snapshot_id=snapshot_id,
            parser_ready=True,
            parser_succeeded=False,
            detail=parse_error or "Deterministic parser failed",
        )

    return CatalogMaterializeResult(
        source_key=discovered.source_key,
        status="candidate_staged",
        source_id=source_id,
        candidate_snapshot_id=snapshot_id,
        parser_ready=True,
        parser_succeeded=True,
        detail="Parsed candidate staged for platform-administrator review and approval",
    )


def _load_existing_source(
    client: SupabaseRestClient,
    source_key: str,
) -> JsonRecord | None:
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_sources",
                params={
                    "source_key": f"eq.{source_key}",
                    "select": (
                        "id,source_key,family,authority,title,edition,landing_url,document_url,"
                        "document_format,parser_key,source_kind,provides_standard_entries,"
                        "catalog_category_key,catalog_category_name,catalog_category_type,"
                        "discovery_status,approved_snapshot_id"
                    ),
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        raise CatalogMaterializeError("Discovered source lookup failed") from error
    if len(rows) > 1:
        raise CatalogMaterializeError("Discovered source key is ambiguous")
    return rows[0] if rows else None


def _upsert_pending_source(
    client: SupabaseRestClient,
    discovered: DiscoveredStandardsSource,
    plan: SourceIngestPlan,
    existing: JsonRecord | None,
) -> UUID:
    payload: JsonRecord = {
        "source_key": discovered.source_key,
        "family": discovered.family,
        "authority": discovered.authority,
        "title": discovered.title,
        "edition": discovered.edition,
        "landing_url": discovered.landing_url,
        "document_url": discovered.document_url,
        "document_format": discovered.document_format,
        "resolver_key": "catalog_discovered_direct",
        "parser_key": plan.parser_key,
        "source_kind": plan.source_kind,
        "provides_standard_entries": plan.provides_standard_entries,
        "catalog_category_key": discovered.category_key,
        "catalog_category_name": discovered.category_name,
        "catalog_category_type": discovered.category_type,
        "discovery_status": "pending",
        "is_active": True,
        "metadata": {
            "source_kind": discovered.source_kind,
            "parser_ready": plan.parser_ready,
            "readiness_detail": plan.readiness_detail,
        },
    }
    try:
        if existing is None:
            rows = _records(
                client.request(
                    "POST",
                    "standard_sources",
                    payload=payload,
                    prefer="return=representation",
                )
            )
        else:
            source_id = _required_uuid(existing, "id")
            rows = _records(
                client.request(
                    "PATCH",
                    "standard_sources",
                    params={"id": f"eq.{source_id}"},
                    payload=payload,
                    prefer="return=representation",
                )
            )
    except SupabaseRestError as error:
        raise CatalogMaterializeError("Pending standards source could not be saved") from error
    if len(rows) != 1:
        raise CatalogMaterializeError("Pending standards source save returned invalid data")
    return _required_uuid(rows[0], "id")


def _stage_candidate_snapshot(
    client: SupabaseRestClient,
    *,
    source_id: UUID,
    discovered: DiscoveredStandardsSource,
    fetched_source_sha256: str,
    resolved_document_url: str,
    normalized_sha256: str,
    parser_key: str,
    parser_version: str | None,
    parser_succeeded: bool,
    parser_error: str | None,
    plan: SourceIngestPlan,
) -> UUID:
    existing = _find_snapshot(client, source_id, fetched_source_sha256)
    provenance: JsonRecord = {
        "catalog_discovery": True,
        "landing_url": discovered.landing_url,
        "observed_document_url": discovered.document_url,
        "parser_key": parser_key,
        "parser_status": "parsed" if parser_succeeded else "failed",
        "source_kind": plan.source_kind,
        "provides_standard_entries": plan.provides_standard_entries,
    }
    if parser_error:
        provenance["parser_error"] = parser_error

    if existing is not None:
        snapshot_id = _required_uuid(existing, "id")
        if _required_text(existing, "status") != "pending":
            raise CatalogMaterializeError(
                "Discovered source fingerprint already has a non-pending snapshot"
            )
        try:
            client.request(
                "PATCH",
                "standard_snapshots",
                params={"id": f"eq.{snapshot_id}"},
                payload={
                    "normalized_sha256": normalized_sha256,
                    "source_version": discovered.edition,
                    "parser_version": parser_version,
                    "resolved_document_url": resolved_document_url,
                    "provenance": provenance,
                },
                prefer="return=minimal",
            )
        except SupabaseRestError as error:
            raise CatalogMaterializeError(
                "Pending discovered snapshot could not be refreshed"
            ) from error
        return snapshot_id

    try:
        rows = _records(
            client.request(
                "POST",
                "standard_snapshots",
                payload={
                    "source_id": str(source_id),
                    "retrieved_at": "now()",
                    "resolved_document_url": resolved_document_url,
                    "source_sha256": fetched_source_sha256,
                    "normalized_sha256": normalized_sha256,
                    "source_version": discovered.edition,
                    "parser_version": parser_version,
                    "status": "pending",
                    "provenance": provenance,
                },
                prefer="return=representation",
            )
        )
    except SupabaseRestError as error:
        raise CatalogMaterializeError("Discovered candidate snapshot could not be staged") from error
    if len(rows) != 1:
        raise CatalogMaterializeError("Discovered candidate snapshot returned invalid data")
    return _required_uuid(rows[0], "id")


def _find_snapshot(
    client: SupabaseRestClient,
    source_id: UUID,
    source_sha256: str,
) -> JsonRecord | None:
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_snapshots",
                params={
                    "source_id": f"eq.{source_id}",
                    "source_sha256": f"eq.{source_sha256}",
                    "select": "id,status",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        raise CatalogMaterializeError("Discovered candidate lookup failed") from error
    if len(rows) > 1:
        raise CatalogMaterializeError("Discovered candidate fingerprint is ambiguous")
    return rows[0] if rows else None


def _reset_snapshot_content(client: SupabaseRestClient, snapshot_id: UUID) -> None:
    try:
        client.request(
            "DELETE",
            "standard_entries",
            params={"snapshot_id": f"eq.{snapshot_id}"},
            prefer="return=minimal",
        )
        client.request(
            "DELETE",
            "standard_snapshot_courses",
            params={"snapshot_id": f"eq.{snapshot_id}"},
            prefer="return=minimal",
        )
    except SupabaseRestError as error:
        raise CatalogMaterializeError("Pending candidate content could not be reset") from error


def _persist_standard_document(
    client: SupabaseRestClient,
    source_id: UUID,
    snapshot_id: UUID,
    parsed: ParsedStandardsDocument,
) -> None:
    _reset_snapshot_content(client, snapshot_id)
    for course_sequence, course in enumerate(parsed.courses, start=1):
        course_id = _upsert_source_course(
            client,
            source_id=source_id,
            course_key=course.course_key,
            display_name=course.display_name,
            source_course_code=course.source_course_code,
            grade_band=course.grade_band,
        )
        _save_snapshot_course(
            client,
            snapshot_id,
            course_id,
            course_sequence,
            course.display_name,
            course.source_course_code,
            course.grade_band,
            provides_entries=True,
        )
        entries = [
            {
                "snapshot_id": str(snapshot_id),
                "course_id": str(course_id),
                "sequence": sequence,
                "code": standard.code,
                "text": standard.text,
                "parent_code": standard.parent_code,
                "strand": standard.strand,
                "metadata": {},
            }
            for sequence, standard in enumerate(course.standards, start=1)
        ]
        try:
            client.request(
                "POST",
                "standard_entries",
                payload=entries,
                prefer="return=minimal",
            )
        except SupabaseRestError as error:
            raise CatalogMaterializeError("Parsed standard entries could not be saved") from error


def _persist_course_catalog(
    client: SupabaseRestClient,
    source_id: UUID,
    snapshot_id: UUID,
    parsed: ParsedCourseCatalogDocument,
) -> None:
    _reset_snapshot_content(client, snapshot_id)
    for course_sequence, course in enumerate(parsed.courses, start=1):
        course_id = _upsert_source_course(
            client,
            source_id=source_id,
            course_key=course.course_key,
            display_name=course.display_name,
            source_course_code=course.source_course_code,
            grade_band=course.grade_band,
        )
        _save_snapshot_course(
            client,
            snapshot_id,
            course_id,
            course_sequence,
            course.display_name,
            course.source_course_code,
            course.grade_band,
            provides_entries=False,
        )


def _upsert_source_course(
    client: SupabaseRestClient,
    *,
    source_id: UUID,
    course_key: str,
    display_name: str,
    source_course_code: str | None,
    grade_band: str | None,
) -> UUID:
    try:
        rows = _records(
            client.request(
                "POST",
                "standard_courses",
                params={"on_conflict": "source_id,course_key"},
                payload={
                    "source_id": str(source_id),
                    "course_key": course_key,
                    "display_name": display_name,
                    "source_course_code": source_course_code,
                    "grade_band": grade_band,
                    "is_pilot_allowed": True,
                    "metadata": {},
                },
                prefer="resolution=merge-duplicates,return=representation",
            )
        )
    except SupabaseRestError as error:
        raise CatalogMaterializeError("Discovered source course could not be saved") from error
    if len(rows) != 1:
        raise CatalogMaterializeError("Discovered source course returned invalid data")
    return _required_uuid(rows[0], "id")


def _save_snapshot_course(
    client: SupabaseRestClient,
    snapshot_id: UUID,
    course_id: UUID,
    sequence: int,
    display_name: str,
    source_course_code: str | None,
    grade_band: str | None,
    *,
    provides_entries: bool,
) -> None:
    try:
        client.request(
            "POST",
            "standard_snapshot_courses",
            payload={
                "snapshot_id": str(snapshot_id),
                "course_id": str(course_id),
                "sequence": sequence,
                "display_name": display_name,
                "source_course_code": source_course_code,
                "grade_band": grade_band,
                "metadata": {"provides_standard_entries": provides_entries},
            },
            prefer="return=minimal",
        )
    except SupabaseRestError as error:
        raise CatalogMaterializeError("Snapshot course manifest could not be saved") from error


def _approved_descriptor_matches(
    existing: JsonRecord,
    discovered: DiscoveredStandardsSource,
) -> bool:
    expected = {
        "family": discovered.family,
        "authority": discovered.authority,
        "title": discovered.title,
        "edition": discovered.edition,
        "landing_url": discovered.landing_url,
        "document_url": discovered.document_url,
        "document_format": discovered.document_format,
        "catalog_category_key": discovered.category_key,
        "catalog_category_name": discovered.category_name,
        "catalog_category_type": discovered.category_type,
    }
    return all(existing.get(key) == value for key, value in expected.items())


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise CatalogMaterializeError("Catalog materialization returned invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _required_text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogMaterializeError(f"Catalog materialization record is missing {key}")
    return value.strip()


def _optional_text(record: JsonRecord, key: str) -> str | None:
    value = record.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _required_uuid(record: JsonRecord, key: str) -> UUID:
    try:
        return UUID(_required_text(record, key))
    except ValueError as error:
        raise CatalogMaterializeError(
            f"Catalog materialization record has invalid {key}"
        ) from error
