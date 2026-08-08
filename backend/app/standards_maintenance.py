from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, cast
from uuid import UUID

from .settings import Settings
from .standards_course_catalog import (
    COURSE_CATALOG_PARSER_VERSION,
    ParsedCourseCatalogDocument,
    parse_course_catalog_document,
)
from .standards_ingest import (
    PARSER_VERSION,
    FetchedSource,
    ParsedStandardsDocument,
    StandardsIngestError,
    extract_document,
    fetch_source,
    parse_document,
)
from .standards_sources import (
    ResolvedStandardsSource,
    StandardsSourceResolutionError,
    resolve_authoritative_document,
)
from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]
CheckStatus = Literal["unchanged", "changed", "unavailable_error"]


class StandardsMaintenanceError(RuntimeError):
    """Bounded failure in the privileged standards-maintenance path."""


@dataclass(frozen=True, slots=True)
class StandardSourceRecord:
    id: UUID
    source_key: str
    landing_url: str
    document_url: str
    document_format: str
    resolver_key: str
    parser_key: str
    source_kind: str
    provides_standard_entries: bool
    approved_snapshot_id: UUID | None


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    id: UUID
    source_sha256: str
    normalized_sha256: str | None
    status: str


@dataclass(frozen=True, slots=True)
class MaintenanceResult:
    source_key: str
    status: CheckStatus
    approved_snapshot_id: UUID | None
    candidate_snapshot_id: UUID | None
    observed_source_sha256: str | None
    normalized_sha256: str | None
    parser_succeeded: bool
    detail: str


def service_role_client(settings: Settings) -> SupabaseRestClient:
    if settings.supabase_url is None or not settings.supabase_service_role_key:
        raise StandardsMaintenanceError("Standards maintenance database access is not configured")
    service_key = settings.supabase_service_role_key
    return SupabaseRestClient(
        base_url=str(settings.supabase_url).rstrip("/"),
        api_key=service_key,
        access_token=service_key,
        timeout_seconds=20.0,
    )


def stage_authoritative_source(
    client: SupabaseRestClient,
    source_key: str,
    *,
    check_month: date | None = None,
) -> MaintenanceResult:
    source = _load_source(client, source_key)
    approved = _load_snapshot(client, source.approved_snapshot_id)

    try:
        resolved = resolve_authoritative_document(source.resolver_key, source.landing_url)
        fetched = fetch_source(resolved.document_url, source.document_format)
    except (StandardsSourceResolutionError, StandardsIngestError) as error:
        detail = str(error)
        if check_month is not None:
            _record_check(
                client,
                source=source,
                check_month=check_month,
                status="unavailable_error",
                approved=approved,
                observed_source_sha256=None,
                candidate_snapshot_id=None,
                resolved_document_url=None,
                error_summary=detail,
                metadata={"phase": "resolve_or_fetch"},
            )
        return MaintenanceResult(
            source_key=source.source_key,
            status="unavailable_error",
            approved_snapshot_id=source.approved_snapshot_id,
            candidate_snapshot_id=None,
            observed_source_sha256=None,
            normalized_sha256=None,
            parser_succeeded=False,
            detail=detail,
        )

    _update_resolved_document_url(client, source, resolved)

    if approved is not None and approved.source_sha256 == fetched.source_sha256:
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
        _record_result_if_requested(client, source, approved, resolved, result, check_month)
        return result

    extracted = None
    parsed_standards: ParsedStandardsDocument | None = None
    parsed_catalog: ParsedCourseCatalogDocument | None = None
    parse_error: str | None = None
    parser_version = PARSER_VERSION
    try:
        extracted = extract_document(fetched)
        if approved is not None and approved.normalized_sha256 == extracted.normalized_sha256:
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
            _record_result_if_requested(client, source, approved, resolved, result, check_month)
            return result

        if source.source_kind == "program_guide":
            parser_version = COURSE_CATALOG_PARSER_VERSION
            parsed_catalog = parse_course_catalog_document(source.parser_key, extracted)
        elif source.provides_standard_entries:
            parsed_standards = parse_document(source.parser_key, extracted)
        else:
            raise StandardsIngestError(
                f"Unsupported governed source role for parser: {source.source_kind}"
            )
    except StandardsIngestError as error:
        parse_error = str(error)

    parser_succeeded = parsed_standards is not None or parsed_catalog is not None
    normalized_sha256 = extracted.normalized_sha256 if extracted is not None else None
    candidate_id = _stage_snapshot(
        client,
        source=source,
        resolved=resolved,
        fetched=fetched,
        normalized_sha256=normalized_sha256,
        parser_key=source.parser_key,
        parser_version=parser_version,
        parser_succeeded=parser_succeeded,
        parser_error=parse_error,
    )

    if parsed_standards is not None:
        _persist_parsed_standards(client, source, candidate_id, parsed_standards)
    elif parsed_catalog is not None:
        _persist_parsed_course_catalog(client, source, candidate_id, parsed_catalog)

    if parsed_catalog is not None:
        detail = "Authoritative course catalog changed and a parsed candidate was staged"
    elif parsed_standards is not None:
        detail = "Authoritative standards content changed and a parsed candidate was staged"
    else:
        detail = "Authoritative source changed; candidate requires parser review before approval"

    result = MaintenanceResult(
        source_key=source.source_key,
        status="changed",
        approved_snapshot_id=source.approved_snapshot_id,
        candidate_snapshot_id=candidate_id,
        observed_source_sha256=fetched.source_sha256,
        normalized_sha256=normalized_sha256,
        parser_succeeded=parser_succeeded,
        detail=detail,
    )
    _record_result_if_requested(
        client,
        source,
        approved,
        resolved,
        result,
        check_month,
        error_summary=parse_error,
    )
    return result


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise StandardsMaintenanceError("Standards maintenance received invalid database data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _required_text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StandardsMaintenanceError(f"Standards maintenance record is missing {key}")
    return value.strip()


def _required_bool(record: JsonRecord, key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise StandardsMaintenanceError(f"Standards maintenance record has invalid {key}")
    return value


def _optional_uuid(record: JsonRecord, key: str) -> UUID | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError as error:
        raise StandardsMaintenanceError(
            f"Standards maintenance record has invalid {key}"
        ) from error


def _load_source(client: SupabaseRestClient, source_key: str) -> StandardSourceRecord:
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_sources",
                params={
                    "source_key": f"eq.{source_key}",
                    "select": (
                        "id,source_key,landing_url,document_url,document_format,"
                        "resolver_key,parser_key,source_kind,provides_standard_entries,"
                        "approved_snapshot_id"
                    ),
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError("Standards source lookup failed") from error
    if len(rows) != 1:
        raise StandardsMaintenanceError("Standards source is missing or ambiguous")
    record = rows[0]
    return StandardSourceRecord(
        id=UUID(_required_text(record, "id")),
        source_key=_required_text(record, "source_key"),
        landing_url=_required_text(record, "landing_url"),
        document_url=_required_text(record, "document_url"),
        document_format=_required_text(record, "document_format"),
        resolver_key=_required_text(record, "resolver_key"),
        parser_key=_required_text(record, "parser_key"),
        source_kind=_required_text(record, "source_kind"),
        provides_standard_entries=_required_bool(record, "provides_standard_entries"),
        approved_snapshot_id=_optional_uuid(record, "approved_snapshot_id"),
    )


def _load_snapshot(
    client: SupabaseRestClient,
    snapshot_id: UUID | None,
) -> SnapshotRecord | None:
    if snapshot_id is None:
        return None
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_snapshots",
                params={
                    "id": f"eq.{snapshot_id}",
                    "select": "id,source_sha256,normalized_sha256,status",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError("Approved standards snapshot lookup failed") from error
    if len(rows) != 1:
        raise StandardsMaintenanceError("Approved standards snapshot is missing or ambiguous")
    record = rows[0]
    normalized = record.get("normalized_sha256")
    return SnapshotRecord(
        id=UUID(_required_text(record, "id")),
        source_sha256=_required_text(record, "source_sha256"),
        normalized_sha256=normalized if isinstance(normalized, str) and normalized else None,
        status=_required_text(record, "status"),
    )


def _update_resolved_document_url(
    client: SupabaseRestClient,
    source: StandardSourceRecord,
    resolved: ResolvedStandardsSource,
) -> None:
    if source.document_url == resolved.document_url:
        return
    try:
        client.request(
            "PATCH",
            "standard_sources",
            params={"id": f"eq.{source.id}"},
            payload={"document_url": resolved.document_url},
            prefer="return=minimal",
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError("Resolved standards URL could not be recorded") from error


def _stage_snapshot(
    client: SupabaseRestClient,
    *,
    source: StandardSourceRecord,
    resolved: ResolvedStandardsSource,
    fetched: FetchedSource,
    normalized_sha256: str | None,
    parser_key: str,
    parser_version: str,
    parser_succeeded: bool,
    parser_error: str | None,
) -> UUID:
    existing = _find_snapshot_by_hash(client, source.id, fetched.source_sha256)
    if existing is not None:
        if existing.status != "pending":
            raise StandardsMaintenanceError(
                "Changed source fingerprint already has a non-pending snapshot"
            )
        return existing.id

    provenance: dict[str, object] = {
        "landing_url": resolved.landing_url,
        "anchor_text": resolved.anchor_text,
        "requested_document_url": resolved.document_url,
        "resolved_document_url": fetched.resolved_url,
        "parser_key": parser_key,
        "parser_status": "parsed" if parser_succeeded else "failed",
        "source_kind": source.source_kind,
        "provides_standard_entries": source.provides_standard_entries,
    }
    if parser_error:
        provenance["parser_error"] = parser_error

    try:
        rows = _records(
            client.request(
                "POST",
                "standard_snapshots",
                payload={
                    "source_id": str(source.id),
                    "resolved_document_url": fetched.resolved_url,
                    "source_sha256": fetched.source_sha256,
                    "normalized_sha256": normalized_sha256,
                    "source_version": resolved.observed_version,
                    "parser_version": parser_version,
                    "status": "pending",
                    "provenance": provenance,
                },
                prefer="return=representation",
            )
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError(
            "Standards candidate snapshot could not be staged"
        ) from error
    if len(rows) != 1:
        raise StandardsMaintenanceError("Standards candidate snapshot save returned invalid data")
    return UUID(_required_text(rows[0], "id"))


def _find_snapshot_by_hash(
    client: SupabaseRestClient,
    source_id: UUID,
    source_sha256: str,
) -> SnapshotRecord | None:
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_snapshots",
                params={
                    "source_id": f"eq.{source_id}",
                    "source_sha256": f"eq.{source_sha256}",
                    "select": "id,source_sha256,normalized_sha256,status",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError("Standards candidate lookup failed") from error
    if not rows:
        return None
    if len(rows) != 1:
        raise StandardsMaintenanceError("Standards candidate fingerprint is ambiguous")
    record = rows[0]
    normalized = record.get("normalized_sha256")
    return SnapshotRecord(
        id=UUID(_required_text(record, "id")),
        source_sha256=_required_text(record, "source_sha256"),
        normalized_sha256=normalized if isinstance(normalized, str) and normalized else None,
        status=_required_text(record, "status"),
    )


def _reset_candidate_content(
    client: SupabaseRestClient,
    snapshot_id: UUID,
) -> None:
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
        raise StandardsMaintenanceError(
            "Existing candidate parsed content could not be reset"
        ) from error


def _persist_parsed_standards(
    client: SupabaseRestClient,
    source: StandardSourceRecord,
    snapshot_id: UUID,
    parsed: ParsedStandardsDocument,
) -> None:
    _reset_candidate_content(client, snapshot_id)
    for course_sequence, course in enumerate(parsed.courses, start=1):
        course_id = _upsert_course(
            client,
            source=source,
            course_key=course.course_key,
            display_name=course.display_name,
            source_course_code=course.source_course_code,
            grade_band=course.grade_band,
        )
        _persist_snapshot_course(
            client,
            snapshot_id=snapshot_id,
            course_id=course_id,
            sequence=course_sequence,
            display_name=course.display_name,
            source_course_code=course.source_course_code,
            grade_band=course.grade_band,
            metadata={"provides_standard_entries": True},
        )
        entries: list[dict[str, object]] = [
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
            raise StandardsMaintenanceError(
                "Parsed standards entries could not be saved"
            ) from error


def _persist_parsed_course_catalog(
    client: SupabaseRestClient,
    source: StandardSourceRecord,
    snapshot_id: UUID,
    parsed: ParsedCourseCatalogDocument,
) -> None:
    _reset_candidate_content(client, snapshot_id)
    for course_sequence, course in enumerate(parsed.courses, start=1):
        course_id = _upsert_course(
            client,
            source=source,
            course_key=course.course_key,
            display_name=course.display_name,
            source_course_code=course.source_course_code,
            grade_band=course.grade_band,
        )
        _persist_snapshot_course(
            client,
            snapshot_id=snapshot_id,
            course_id=course_id,
            sequence=course_sequence,
            display_name=course.display_name,
            source_course_code=course.source_course_code,
            grade_band=course.grade_band,
            metadata={"provides_standard_entries": False},
        )


def _persist_snapshot_course(
    client: SupabaseRestClient,
    *,
    snapshot_id: UUID,
    course_id: UUID,
    sequence: int,
    display_name: str,
    source_course_code: str | None,
    grade_band: str | None,
    metadata: dict[str, object],
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
                "metadata": metadata,
            },
            prefer="return=minimal",
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError(
            "Parsed snapshot course manifest could not be saved"
        ) from error


def _upsert_course(
    client: SupabaseRestClient,
    *,
    source: StandardSourceRecord,
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
                    "source_id": str(source.id),
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
        raise StandardsMaintenanceError("Standards course could not be saved") from error
    if len(rows) != 1:
        raise StandardsMaintenanceError("Standards course save returned invalid data")
    return UUID(_required_text(rows[0], "id"))


def _record_result_if_requested(
    client: SupabaseRestClient,
    source: StandardSourceRecord,
    approved: SnapshotRecord | None,
    resolved: ResolvedStandardsSource,
    result: MaintenanceResult,
    check_month: date | None,
    *,
    error_summary: str | None = None,
) -> None:
    if check_month is None:
        return
    _record_check(
        client,
        source=source,
        check_month=check_month,
        status=result.status,
        approved=approved,
        observed_source_sha256=result.observed_source_sha256,
        candidate_snapshot_id=result.candidate_snapshot_id,
        resolved_document_url=resolved.document_url,
        error_summary=error_summary,
        metadata={
            "normalized_sha256": result.normalized_sha256,
            "parser_succeeded": result.parser_succeeded,
            "detail": result.detail,
            "source_kind": source.source_kind,
        },
    )


def _record_check(
    client: SupabaseRestClient,
    *,
    source: StandardSourceRecord,
    check_month: date,
    status: CheckStatus,
    approved: SnapshotRecord | None,
    observed_source_sha256: str | None,
    candidate_snapshot_id: UUID | None,
    resolved_document_url: str | None,
    error_summary: str | None,
    metadata: dict[str, object],
) -> None:
    month = check_month.replace(day=1)
    try:
        client.request(
            "POST",
            "standard_source_checks",
            params={"on_conflict": "source_id,check_month"},
            payload={
                "source_id": str(source.id),
                "check_month": month.isoformat(),
                "result_status": status,
                "approved_snapshot_id_before": str(approved.id) if approved else None,
                "observed_source_sha256": observed_source_sha256,
                "candidate_snapshot_id": (
                    str(candidate_snapshot_id) if candidate_snapshot_id else None
                ),
                "resolved_document_url": resolved_document_url,
                "error_summary": error_summary,
                "metadata": metadata,
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError("Standards monthly check could not be recorded") from error
