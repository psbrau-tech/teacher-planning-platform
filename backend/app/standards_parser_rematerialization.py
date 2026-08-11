from __future__ import annotations

from datetime import date
from typing import Any, cast
from uuid import UUID

from .standards_ingest import StandardsIngestError, extract_document, fetch_source
from .standards_maintenance import (
    MaintenanceResult,
    StandardsMaintenanceError,
    _load_source,
    _persist_parsed_standards,
    _records,
    _required_text,
    _update_resolved_document_url,
    parse_document,
)
from .standards_sources import StandardsSourceResolutionError, resolve_authoritative_document
from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]


def stage_parser_rematerialization_if_needed(
    client: SupabaseRestClient,
    source_key: str,
    *,
    check_date: date,
) -> MaintenanceResult | None:
    """Stage a new immutable candidate when reviewed parser logic changes.

    Normal source reconciliation intentionally fingerprints the authoritative file. A parser
    upgrade can change deterministic materialization even when that source file is byte-for-byte
    unchanged. In that case this path stages a new pending snapshot keyed by source hash plus
    parser version; the currently approved snapshot remains active until explicit approval.
    """

    source = _load_source(client, source_key)
    if not source.provides_standard_entries or source.approved_snapshot_id is None:
        return None

    approved = _load_approved_materialization(client, source.approved_snapshot_id)

    try:
        resolved = resolve_authoritative_document(source.resolver_key, source.landing_url)
        fetched = fetch_source(resolved.document_url, source.document_format)
        extracted = extract_document(fetched)
        parsed = parse_document(source.parser_key, extracted)
    except (StandardsSourceResolutionError, StandardsIngestError) as error:
        raise StandardsMaintenanceError(
            f"Parser rematerialization could not read {source.source_key}: {error}"
        ) from error

    current_parser_version = parsed.parser_version.strip()
    if not current_parser_version:
        raise StandardsMaintenanceError("Parser rematerialization produced an empty parser version")

    if approved["parser_version"] == current_parser_version:
        return None

    # A simultaneous authoritative-content change belongs to the normal reconciliation path.
    # Parser rematerialization is only for the same normalized authoritative content.
    if approved["normalized_sha256"] != extracted.normalized_sha256:
        return None

    _update_resolved_document_url(client, source, resolved)
    candidate_id = _stage_parser_version_candidate(
        client,
        source_id=source.id,
        source_key=source.source_key,
        approved_snapshot_id=source.approved_snapshot_id,
        resolved_document_url=fetched.resolved_url,
        landing_url=resolved.landing_url,
        anchor_text=resolved.anchor_text,
        requested_document_url=resolved.document_url,
        source_sha256=fetched.source_sha256,
        normalized_sha256=extracted.normalized_sha256,
        source_version=resolved.observed_version,
        parser_key=source.parser_key,
        parser_version=current_parser_version,
        source_kind=source.source_kind,
    )
    _persist_parsed_standards(client, source, candidate_id, parsed)

    detail = (
        "Authoritative source content is unchanged, but reviewed parser logic changed from "
        f"{approved['parser_version'] or 'unversioned'} to {current_parser_version}; "
        "a new materialized candidate was staged for administrator approval"
    )
    result = MaintenanceResult(
        source_key=source.source_key,
        status="changed",
        approved_snapshot_id=source.approved_snapshot_id,
        candidate_snapshot_id=candidate_id,
        observed_source_sha256=fetched.source_sha256,
        normalized_sha256=extracted.normalized_sha256,
        parser_succeeded=True,
        detail=detail,
    )
    _mark_source_check_as_parser_change(
        client,
        source_id=source.id,
        check_date=check_date,
        approved_snapshot_id=source.approved_snapshot_id,
        candidate_snapshot_id=candidate_id,
        source_sha256=fetched.source_sha256,
        parser_version_before=cast(str | None, approved["parser_version"]),
        parser_version_after=current_parser_version,
        normalized_sha256=extracted.normalized_sha256,
    )
    return result


def _load_approved_materialization(
    client: SupabaseRestClient,
    snapshot_id: UUID,
) -> JsonRecord:
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_snapshots",
                params={
                    "id": f"eq.{snapshot_id}",
                    "select": "id,source_sha256,normalized_sha256,parser_version,status",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError(
            "Approved standards materialization lookup failed"
        ) from error
    if len(rows) != 1:
        raise StandardsMaintenanceError(
            "Approved standards materialization is missing or ambiguous"
        )
    record = rows[0]
    if _required_text(record, "status") != "approved":
        raise StandardsMaintenanceError("Configured standards snapshot is not approved")
    normalized = record.get("normalized_sha256")
    if not isinstance(normalized, str) or not normalized.strip():
        raise StandardsMaintenanceError(
            "Approved standards materialization lacks a normalized source hash"
        )
    parser_version = record.get("parser_version")
    if parser_version is not None and not isinstance(parser_version, str):
        raise StandardsMaintenanceError("Approved standards parser version is invalid")
    return {
        "normalized_sha256": normalized.strip(),
        "parser_version": parser_version.strip() if isinstance(parser_version, str) else None,
    }


def _stage_parser_version_candidate(
    client: SupabaseRestClient,
    *,
    source_id: UUID,
    source_key: str,
    approved_snapshot_id: UUID,
    resolved_document_url: str,
    landing_url: str,
    anchor_text: str | None,
    requested_document_url: str,
    source_sha256: str,
    normalized_sha256: str,
    source_version: str | None,
    parser_key: str,
    parser_version: str,
    source_kind: str,
) -> UUID:
    try:
        existing = _records(
            client.request(
                "GET",
                "standard_snapshots",
                params={
                    "source_id": f"eq.{source_id}",
                    "source_sha256": f"eq.{source_sha256}",
                    "parser_version": f"eq.{parser_version}",
                    "select": "id,status",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError(
            "Parser-version standards candidate lookup failed"
        ) from error

    provenance: JsonRecord = {
        "landing_url": landing_url,
        "anchor_text": anchor_text,
        "requested_document_url": requested_document_url,
        "resolved_document_url": resolved_document_url,
        "parser_key": parser_key,
        "parser_status": "parsed",
        "source_kind": source_kind,
        "provides_standard_entries": True,
        "rematerialized_from_snapshot_id": str(approved_snapshot_id),
        "rematerialization_reason": "reviewed_parser_version_change",
    }

    if existing:
        if len(existing) != 1:
            raise StandardsMaintenanceError(
                "Parser-version standards candidate is ambiguous"
            )
        status = _required_text(existing[0], "status")
        candidate_id = UUID(_required_text(existing[0], "id"))
        if status != "pending":
            raise StandardsMaintenanceError(
                f"Parser version {parser_version} already has a non-pending "
                f"snapshot for {source_key}"
            )
        try:
            client.request(
                "PATCH",
                "standard_snapshots",
                params={"id": f"eq.{candidate_id}"},
                payload={
                    "resolved_document_url": resolved_document_url,
                    "normalized_sha256": normalized_sha256,
                    "source_version": source_version,
                    "provenance": provenance,
                },
                prefer="return=minimal",
            )
        except SupabaseRestError as error:
            raise StandardsMaintenanceError(
                "Pending parser-version candidate could not be refreshed"
            ) from error
        return candidate_id

    try:
        rows = _records(
            client.request(
                "POST",
                "standard_snapshots",
                payload={
                    "source_id": str(source_id),
                    "resolved_document_url": resolved_document_url,
                    "source_sha256": source_sha256,
                    "normalized_sha256": normalized_sha256,
                    "source_version": source_version,
                    "parser_version": parser_version,
                    "status": "pending",
                    "provenance": provenance,
                },
                prefer="return=representation",
            )
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError(
            "Parser-version standards candidate could not be staged"
        ) from error
    if len(rows) != 1:
        raise StandardsMaintenanceError(
            "Parser-version standards candidate save returned invalid data"
        )
    return UUID(_required_text(rows[0], "id"))


def _mark_source_check_as_parser_change(
    client: SupabaseRestClient,
    *,
    source_id: UUID,
    check_date: date,
    approved_snapshot_id: UUID,
    candidate_snapshot_id: UUID,
    source_sha256: str,
    parser_version_before: str | None,
    parser_version_after: str,
    normalized_sha256: str,
) -> None:
    check_month = check_date.replace(day=1).isoformat()
    metadata: JsonRecord = {
        "detail": "Authoritative source unchanged; reviewed parser version changed",
        "parser_succeeded": True,
        "parser_version_before": parser_version_before,
        "parser_version_after": parser_version_after,
        "normalized_sha256": normalized_sha256,
        "rematerialization_reason": "reviewed_parser_version_change",
    }
    try:
        client.request(
            "PATCH",
            "standard_source_checks",
            params={
                "source_id": f"eq.{source_id}",
                "check_month": f"eq.{check_month}",
            },
            payload={
                "result_status": "changed",
                "approved_snapshot_id_before": str(approved_snapshot_id),
                "observed_source_sha256": source_sha256,
                "candidate_snapshot_id": str(candidate_snapshot_id),
                "error_summary": None,
                "metadata": metadata,
            },
            prefer="return=minimal",
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError(
            "Parser-version standards source check could not be recorded"
        ) from error
