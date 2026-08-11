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
    parse_document,
)
from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]


def stage_pending_parser_rematerialization_if_needed(
    client: SupabaseRestClient,
    source_key: str,
    *,
    check_date: date,
) -> MaintenanceResult | None:
    """Stage a distinct parser-version candidate for a not-yet-approved source.

    Newly discovered catalog sources can expose parser defects during administrator review before
    their first snapshot is approved. Preserve the original pending candidate as audit evidence and
    stage the reviewed parser correction under the same authoritative source hash plus a new parser
    version. Explicit administrator approval remains a separate action.
    """

    source = _load_source(client, source_key)
    if source.approved_snapshot_id is not None or not source.provides_standard_entries:
        return None

    try:
        fetched = fetch_source(source.document_url, source.document_format)
        extracted = extract_document(fetched)
        parsed = parse_document(source.parser_key, extracted)
    except StandardsIngestError as error:
        raise StandardsMaintenanceError(
            f"Pending parser rematerialization could not read {source.source_key}: {error}"
        ) from error

    parser_version = parsed.parser_version.strip()
    if not parser_version:
        raise StandardsMaintenanceError(
            "Pending parser rematerialization produced an empty parser version"
        )

    candidates = _load_same_source_candidates(
        client,
        source_id=source.id,
        source_sha256=fetched.source_sha256,
    )
    if not candidates:
        return None

    baseline = next(
        (
            row
            for row in candidates
            if _optional_text(row, "parser_version") != parser_version
            and _required_text(row, "status") == "pending"
        ),
        None,
    )
    current = next(
        (
            row
            for row in candidates
            if _optional_text(row, "parser_version") == parser_version
        ),
        None,
    )

    if baseline is None and current is None:
        return None

    if baseline is not None:
        baseline_normalized = _required_text(baseline, "normalized_sha256")
        if baseline_normalized != extracted.normalized_sha256:
            raise StandardsMaintenanceError(
                "Pending parser rematerialization source normalization changed unexpectedly"
            )

    baseline_id = UUID(
        _required_text(baseline or current or {}, "id")
    )
    source_version = _optional_text(baseline or current or {}, "source_version")

    candidate_id = _stage_parser_version_candidate(
        client,
        source_id=source.id,
        source_key=source.source_key,
        baseline_snapshot_id=baseline_id,
        source_sha256=fetched.source_sha256,
        normalized_sha256=extracted.normalized_sha256,
        source_version=source_version,
        resolved_document_url=fetched.resolved_url,
        parser_key=source.parser_key,
        parser_version=parser_version,
        source_kind=source.source_kind,
        existing=current,
    )
    _persist_parsed_standards(client, source, candidate_id, parsed)
    _mark_source_check_as_pending_parser_change(
        client,
        source_id=source.id,
        check_date=check_date,
        baseline_snapshot_id=baseline_id,
        candidate_snapshot_id=candidate_id,
        source_sha256=fetched.source_sha256,
        parser_version_before=(
            _optional_text(baseline, "parser_version") if baseline is not None else None
        ),
        parser_version_after=parser_version,
        normalized_sha256=extracted.normalized_sha256,
    )

    return MaintenanceResult(
        source_key=source.source_key,
        status="changed",
        approved_snapshot_id=None,
        candidate_snapshot_id=candidate_id,
        observed_source_sha256=fetched.source_sha256,
        normalized_sha256=extracted.normalized_sha256,
        parser_succeeded=True,
        detail=(
            "Not-yet-approved authoritative source is unchanged, but reviewed parser logic "
            f"changed to {parser_version}; a distinct pending materialization was staged"
        ),
    )


def _load_same_source_candidates(
    client: SupabaseRestClient,
    *,
    source_id: UUID,
    source_sha256: str,
) -> list[JsonRecord]:
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_snapshots",
                params={
                    "source_id": f"eq.{source_id}",
                    "source_sha256": f"eq.{source_sha256}",
                    "select": (
                        "id,status,parser_version,normalized_sha256,source_version,retrieved_at"
                    ),
                    "order": "retrieved_at.asc",
                },
            )
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError(
            "Pending parser-version candidate lookup failed"
        ) from error
    return rows


def _stage_parser_version_candidate(
    client: SupabaseRestClient,
    *,
    source_id: UUID,
    source_key: str,
    baseline_snapshot_id: UUID,
    source_sha256: str,
    normalized_sha256: str,
    source_version: str | None,
    resolved_document_url: str,
    parser_key: str,
    parser_version: str,
    source_kind: str,
    existing: JsonRecord | None,
) -> UUID:
    provenance: JsonRecord = {
        "resolved_document_url": resolved_document_url,
        "parser_key": parser_key,
        "parser_status": "parsed",
        "source_kind": source_kind,
        "provides_standard_entries": True,
        "rematerialized_from_snapshot_id": str(baseline_snapshot_id),
        "rematerialization_reason": "reviewed_parser_version_change_before_initial_approval",
    }

    if existing is not None:
        status = _required_text(existing, "status")
        candidate_id = UUID(_required_text(existing, "id"))
        if status != "pending":
            raise StandardsMaintenanceError(
                f"Parser version {parser_version} already has a non-pending snapshot for "
                f"{source_key}"
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
            "Pending parser-version candidate could not be staged"
        ) from error
    if len(rows) != 1:
        raise StandardsMaintenanceError(
            "Pending parser-version candidate save returned invalid data"
        )
    return UUID(_required_text(rows[0], "id"))


def _mark_source_check_as_pending_parser_change(
    client: SupabaseRestClient,
    *,
    source_id: UUID,
    check_date: date,
    baseline_snapshot_id: UUID,
    candidate_snapshot_id: UUID,
    source_sha256: str,
    parser_version_before: str | None,
    parser_version_after: str,
    normalized_sha256: str,
) -> None:
    metadata: JsonRecord = {
        "detail": "Pending authoritative source unchanged; reviewed parser version changed",
        "parser_succeeded": True,
        "parser_version_before": parser_version_before,
        "parser_version_after": parser_version_after,
        "normalized_sha256": normalized_sha256,
        "rematerialization_reason": "reviewed_parser_version_change_before_initial_approval",
        "baseline_snapshot_id": str(baseline_snapshot_id),
    }
    try:
        client.request(
            "POST",
            "standard_source_checks",
            params={"on_conflict": "source_id,check_month"},
            payload={
                "source_id": str(source_id),
                "check_month": check_date.replace(day=1).isoformat(),
                "result_status": "changed",
                "approved_snapshot_id_before": None,
                "observed_source_sha256": source_sha256,
                "candidate_snapshot_id": str(candidate_snapshot_id),
                "error_summary": None,
                "metadata": metadata,
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )
    except SupabaseRestError as error:
        raise StandardsMaintenanceError(
            "Pending parser-version source check could not be recorded"
        ) from error


def _optional_text(record: JsonRecord | None, key: str) -> str | None:
    if record is None:
        return None
    value = record.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None
