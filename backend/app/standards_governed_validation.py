from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, cast
from uuid import UUID

from .standards_course_catalog import parse_course_catalog_document
from .standards_ingest import StandardsIngestError, extract_document, fetch_source
from .standards_maintenance import MaintenanceResult, stage_authoritative_source
from .standards_parser_dispatch import parse_governed_standards_document
from .standards_source_resolver import resolve_governed_source_document
from .standards_sources import StandardsSourceResolutionError
from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]
CheckStatus = Literal["unchanged", "changed", "unavailable_error"]


class GovernedStandardsValidationError(RuntimeError):
    """Bounded failure while validating an approved governed standards source."""


@dataclass(frozen=True, slots=True)
class _Source:
    id: UUID
    source_key: str
    title: str
    edition: str
    landing_url: str
    document_url: str
    document_format: str
    resolver_key: str
    parser_key: str
    source_kind: str
    provides_standard_entries: bool
    approved_snapshot_id: UUID | None


@dataclass(frozen=True, slots=True)
class _Snapshot:
    id: UUID
    source_sha256: str
    normalized_sha256: str | None


def validate_governed_source(
    client: SupabaseRestClient,
    source_key: str,
    *,
    check_month: date | None = None,
) -> MaintenanceResult:
    source = _load_source(client, source_key)
    if source.resolver_key != "catalog_discovered_direct":
        return stage_authoritative_source(client, source_key, check_month=check_month)

    approved = _load_approved_snapshot(client, source.approved_snapshot_id)
    if approved is None:
        raise GovernedStandardsValidationError(
            "Approved catalog-discovered source has no approved snapshot"
        )

    try:
        resolved = resolve_governed_source_document(
            resolver_key=source.resolver_key,
            landing_url=source.landing_url,
            document_url=source.document_url,
            source_title=source.title,
            source_edition=source.edition,
        )
        fetched = fetch_source(resolved.document_url, source.document_format)
    except (StandardsSourceResolutionError, StandardsIngestError) as error:
        result = MaintenanceResult(
            source_key=source.source_key,
            status="unavailable_error",
            approved_snapshot_id=approved.id,
            candidate_snapshot_id=None,
            observed_source_sha256=None,
            normalized_sha256=None,
            parser_succeeded=False,
            detail=str(error),
        )
        _record_if_requested(client, source, approved, result, check_month)
        return result

    if fetched.source_sha256 == approved.source_sha256:
        result = MaintenanceResult(
            source_key=source.source_key,
            status="unchanged",
            approved_snapshot_id=approved.id,
            candidate_snapshot_id=None,
            observed_source_sha256=fetched.source_sha256,
            normalized_sha256=approved.normalized_sha256,
            parser_succeeded=True,
            detail="Authoritative source fingerprint is unchanged",
        )
        _record_if_requested(client, source, approved, result, check_month)
        return result

    extracted = extract_document(fetched)
    if approved.normalized_sha256 == extracted.normalized_sha256:
        result = MaintenanceResult(
            source_key=source.source_key,
            status="unchanged",
            approved_snapshot_id=approved.id,
            candidate_snapshot_id=None,
            observed_source_sha256=fetched.source_sha256,
            normalized_sha256=extracted.normalized_sha256,
            parser_succeeded=True,
            detail="Raw file changed but normalized authoritative content is unchanged",
        )
        _record_if_requested(client, source, approved, result, check_month)
        return result

    parsed_standards = None
    parsed_catalog = None
    parse_error: str | None = None
    parser_version: str | None = None
    try:
        if source.source_kind == "program_guide":
            parsed_catalog = parse_course_catalog_document(source.parser_key, extracted)
            parser_version = parsed_catalog.parser_version
        elif source.provides_standard_entries:
            parsed_standards = parse_governed_standards_document(
                source.parser_key,
                extracted,
            )
            parser_version = parsed_standards.parser_version
        else:
            raise StandardsIngestError(
                f"Unsupported governed source role: {source.source_kind}"
            )
    except StandardsIngestError as error:
        parse_error = str(error)

    parser_succeeded = parsed_standards is not None or parsed_catalog is not None
    candidate_id = _stage_pending_snapshot(
        client,
        source=source,
        source_sha256=fetched.source_sha256,
        resolved_document_url=fetched.resolved_url,
        normalized_sha256=extracted.normalized_sha256,
        parser_version=parser_version,
        parser_succeeded=parser_succeeded,
        parser_error=parse_error,
    )

    if parsed_standards is not None:
        _persist_standards(client, source, candidate_id, parsed_standards)
    elif parsed_catalog is not None:
        _persist_course_catalog(client, source, candidate_id, parsed_catalog)

    result = MaintenanceResult(
        source_key=source.source_key,
        status="changed",
        approved_snapshot_id=approved.id,
        candidate_snapshot_id=candidate_id,
        observed_source_sha256=fetched.source_sha256,
        normalized_sha256=extracted.normalized_sha256,
        parser_succeeded=parser_succeeded,
        detail=(
            "Authoritative source changed and a parsed candidate was staged"
            if parser_succeeded
            else "Authoritative source changed; candidate requires parser review"
        ),
    )
    _record_if_requested(
        client,
        source,
        approved,
        result,
        check_month,
        error_summary=parse_error,
    )
    return result


def _load_source(client: SupabaseRestClient, source_key: str) -> _Source:
    rows = _request_records(
        client,
        "GET",
        "standard_sources",
        params={
            "source_key": f"eq.{source_key}",
            "discovery_status": "eq.approved",
            "select": (
                "id,source_key,title,edition,landing_url,document_url,document_format,"
                "resolver_key,parser_key,source_kind,provides_standard_entries,"
                "approved_snapshot_id"
            ),
            "limit": "2",
        },
    )
    if len(rows) != 1:
        raise GovernedStandardsValidationError(
            "Governed standards source is missing or ambiguous"
        )
    row = rows[0]
    return _Source(
        id=_uuid(row, "id"),
        source_key=_text(row, "source_key"),
        title=_text(row, "title"),
        edition=_text(row, "edition"),
        landing_url=_text(row, "landing_url"),
        document_url=_text(row, "document_url"),
        document_format=_text(row, "document_format"),
        resolver_key=_text(row, "resolver_key"),
        parser_key=_text(row, "parser_key"),
        source_kind=_text(row, "source_kind"),
        provides_standard_entries=_bool(row, "provides_standard_entries"),
        approved_snapshot_id=_optional_uuid(row, "approved_snapshot_id"),
    )


def _load_approved_snapshot(
    client: SupabaseRestClient,
    snapshot_id: UUID | None,
) -> _Snapshot | None:
    if snapshot_id is None:
        return None
    rows = _request_records(
        client,
        "GET",
        "standard_snapshots",
        params={
            "id": f"eq.{snapshot_id}",
            "status": "eq.approved",
            "select": "id,source_sha256,normalized_sha256",
            "limit": "2",
        },
    )
    if len(rows) != 1:
        return None
    normalized = rows[0].get("normalized_sha256")
    return _Snapshot(
        id=_uuid(rows[0], "id"),
        source_sha256=_text(rows[0], "source_sha256"),
        normalized_sha256=(
            normalized if isinstance(normalized, str) and normalized.strip() else None
        ),
    )


def _stage_pending_snapshot(
    client: SupabaseRestClient,
    *,
    source: _Source,
    source_sha256: str,
    resolved_document_url: str,
    normalized_sha256: str,
    parser_version: str | None,
    parser_succeeded: bool,
    parser_error: str | None,
) -> UUID:
    existing = _request_records(
        client,
        "GET",
        "standard_snapshots",
        params={
            "source_id": f"eq.{source.id}",
            "source_sha256": f"eq.{source_sha256}",
            "select": "id,status",
            "limit": "2",
        },
    )
    provenance: JsonRecord = {
        "landing_url": source.landing_url,
        "resolved_document_url": resolved_document_url,
        "parser_key": source.parser_key,
        "parser_status": "parsed" if parser_succeeded else "failed",
        "source_kind": source.source_kind,
        "provides_standard_entries": source.provides_standard_entries,
    }
    if parser_error:
        provenance["parser_error"] = parser_error

    if existing:
        if len(existing) != 1 or _text(existing[0], "status") != "pending":
            raise GovernedStandardsValidationError(
                "Changed source fingerprint already has a non-pending snapshot"
            )
        snapshot_id = _uuid(existing[0], "id")
        _request(
            client,
            "PATCH",
            "standard_snapshots",
            params={"id": f"eq.{snapshot_id}"},
            payload={
                "normalized_sha256": normalized_sha256,
                "source_version": source.edition,
                "parser_version": parser_version,
                "resolved_document_url": resolved_document_url,
                "provenance": provenance,
            },
            prefer="return=minimal",
        )
        return snapshot_id

    rows = _request_records(
        client,
        "POST",
        "standard_snapshots",
        payload={
            "source_id": str(source.id),
            "resolved_document_url": resolved_document_url,
            "source_sha256": source_sha256,
            "normalized_sha256": normalized_sha256,
            "source_version": source.edition,
            "parser_version": parser_version,
            "status": "pending",
            "provenance": provenance,
        },
        prefer="return=representation",
    )
    if len(rows) != 1:
        raise GovernedStandardsValidationError(
            "Changed governed source candidate returned invalid data"
        )
    return _uuid(rows[0], "id")


def _persist_standards(client, source, snapshot_id, parsed) -> None:
    _reset_candidate(client, snapshot_id)
    for sequence, course in enumerate(parsed.courses, start=1):
        course_id = _upsert_course(
            client,
            source.id,
            course.course_key,
            course.display_name,
            course.source_course_code,
            course.grade_band,
        )
        _persist_manifest(
            client,
            snapshot_id,
            course_id,
            sequence,
            course.display_name,
            course.source_course_code,
            course.grade_band,
            True,
        )
        entries = [
            {
                "snapshot_id": str(snapshot_id),
                "course_id": str(course_id),
                "sequence": entry_sequence,
                "code": standard.code,
                "text": standard.text,
                "parent_code": standard.parent_code,
                "strand": standard.strand,
                "metadata": {},
            }
            for entry_sequence, standard in enumerate(course.standards, start=1)
        ]
        _request(
            client,
            "POST",
            "standard_entries",
            payload=entries,
            prefer="return=minimal",
        )


def _persist_course_catalog(client, source, snapshot_id, parsed) -> None:
    _reset_candidate(client, snapshot_id)
    for sequence, course in enumerate(parsed.courses, start=1):
        course_id = _upsert_course(
            client,
            source.id,
            course.course_key,
            course.display_name,
            course.source_course_code,
            course.grade_band,
        )
        _persist_manifest(
            client,
            snapshot_id,
            course_id,
            sequence,
            course.display_name,
            course.source_course_code,
            course.grade_band,
            False,
        )


def _reset_candidate(client: SupabaseRestClient, snapshot_id: UUID) -> None:
    _request(
        client,
        "DELETE",
        "standard_entries",
        params={"snapshot_id": f"eq.{snapshot_id}"},
        prefer="return=minimal",
    )
    _request(
        client,
        "DELETE",
        "standard_snapshot_courses",
        params={"snapshot_id": f"eq.{snapshot_id}"},
        prefer="return=minimal",
    )


def _upsert_course(
    client: SupabaseRestClient,
    source_id: UUID,
    course_key: str,
    display_name: str,
    source_course_code: str | None,
    grade_band: str | None,
) -> UUID:
    rows = _request_records(
        client,
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
    if len(rows) != 1:
        raise GovernedStandardsValidationError("Governed source course save returned invalid data")
    return _uuid(rows[0], "id")


def _persist_manifest(
    client: SupabaseRestClient,
    snapshot_id: UUID,
    course_id: UUID,
    sequence: int,
    display_name: str,
    source_course_code: str | None,
    grade_band: str | None,
    provides_entries: bool,
) -> None:
    _request(
        client,
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


def _record_if_requested(
    client: SupabaseRestClient,
    source: _Source,
    approved: _Snapshot,
    result: MaintenanceResult,
    check_month: date | None,
    *,
    error_summary: str | None = None,
) -> None:
    if check_month is None:
        return
    month = check_month.replace(day=1)
    _request(
        client,
        "POST",
        "standard_source_checks",
        params={"on_conflict": "source_id,check_month"},
        payload={
            "source_id": str(source.id),
            "check_month": month.isoformat(),
            "result_status": result.status,
            "approved_snapshot_id_before": str(approved.id),
            "observed_source_sha256": result.observed_source_sha256,
            "candidate_snapshot_id": (
                str(result.candidate_snapshot_id) if result.candidate_snapshot_id else None
            ),
            "resolved_document_url": source.document_url,
            "error_summary": error_summary,
            "metadata": {
                "normalized_sha256": result.normalized_sha256,
                "parser_succeeded": result.parser_succeeded,
                "detail": result.detail,
                "source_kind": source.source_kind,
            },
        },
        prefer="resolution=merge-duplicates,return=minimal",
    )


def _request_records(
    client: SupabaseRestClient,
    method: str,
    resource: str,
    *,
    params: dict[str, str] | None = None,
    payload: object | None = None,
    prefer: str | None = None,
) -> list[JsonRecord]:
    result = _request(
        client,
        method,
        resource,
        params=params,
        payload=payload,
        prefer=prefer,
    )
    if not isinstance(result, list):
        raise GovernedStandardsValidationError(
            "Governed standards validation returned invalid data"
        )
    return [cast(JsonRecord, item) for item in result if isinstance(item, dict)]


def _request(
    client: SupabaseRestClient,
    method: str,
    resource: str,
    *,
    params: dict[str, str] | None = None,
    payload: object | None = None,
    prefer: str | None = None,
) -> object:
    try:
        return client.request(
            method,
            resource,
            params=params,
            payload=payload,
            prefer=prefer,
        )
    except SupabaseRestError as error:
        raise GovernedStandardsValidationError(
            "Governed standards validation database operation failed"
        ) from error


def _text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GovernedStandardsValidationError(
            f"Governed standards validation record is missing {key}"
        )
    return value.strip()


def _uuid(record: JsonRecord, key: str) -> UUID:
    try:
        return UUID(_text(record, key))
    except ValueError as error:
        raise GovernedStandardsValidationError(
            f"Governed standards validation record has invalid {key}"
        ) from error


def _optional_uuid(record: JsonRecord, key: str) -> UUID | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError as error:
        raise GovernedStandardsValidationError(
            f"Governed standards validation record has invalid {key}"
        ) from error


def _bool(record: JsonRecord, key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise GovernedStandardsValidationError(
            f"Governed standards validation record has invalid {key}"
        )
    return value
