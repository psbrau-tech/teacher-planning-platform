from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, cast
from uuid import UUID

from .standards_ingest import StandardsIngestError, extract_document, fetch_source
from .standards_maintenance import MaintenanceResult
from .standards_proficiency import parse_alabama_ela_proficiency
from .standards_sources import StandardsSourceResolutionError, resolve_authoritative_document
from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]


class ProficiencyMaintenanceError(RuntimeError):
    """Bounded failure while reconciling governed ALSDE proficiency guidance."""


@dataclass(frozen=True, slots=True)
class _Source:
    id: UUID
    source_key: str
    landing_url: str
    document_format: str
    resolver_key: str
    parser_key: str
    approved_snapshot_id: UUID | None


@dataclass(frozen=True, slots=True)
class _Snapshot:
    id: UUID
    source_sha256: str
    normalized_sha256: str


def is_proficiency_source_key(source_key: str) -> bool:
    return source_key.startswith("alabama_ela_proficiency_grade_")


def proficiency_source_keys() -> tuple[str, ...]:
    return tuple(f"alabama_ela_proficiency_grade_{grade}" for grade in range(6, 13))


def validate_proficiency_source(
    client: SupabaseRestClient,
    source_key: str,
    *,
    check_month: date | None = None,
) -> MaintenanceResult:
    if not is_proficiency_source_key(source_key):
        raise ProficiencyMaintenanceError("Unsupported proficiency-scale source key")

    source = _load_source(client, source_key)
    approved = _load_snapshot(client, source.approved_snapshot_id)

    try:
        resolved = resolve_authoritative_document(source.resolver_key, source.landing_url)
        fetched = fetch_source(resolved.document_url, source.document_format)
    except (StandardsSourceResolutionError, StandardsIngestError) as error:
        result = MaintenanceResult(
            source_key=source.source_key,
            status="unavailable_error",
            approved_snapshot_id=approved.id if approved else None,
            candidate_snapshot_id=None,
            observed_source_sha256=None,
            normalized_sha256=None,
            parser_succeeded=False,
            detail=str(error),
        )
        _record_if_requested(client, source, approved, result, check_month, error_summary=str(error))
        return result

    _update_resolved_url(client, source.id, fetched.resolved_url)

    if approved is not None and fetched.source_sha256 == approved.source_sha256:
        result = MaintenanceResult(
            source_key=source.source_key,
            status="unchanged",
            approved_snapshot_id=approved.id,
            candidate_snapshot_id=None,
            observed_source_sha256=fetched.source_sha256,
            normalized_sha256=approved.normalized_sha256,
            parser_succeeded=True,
            detail="Current ALSDE proficiency source fingerprint is unchanged",
        )
        _record_if_requested(client, source, approved, result, check_month)
        return result

    try:
        extracted = extract_document(fetched)
    except StandardsIngestError as error:
        result = MaintenanceResult(
            source_key=source.source_key,
            status="unavailable_error",
            approved_snapshot_id=approved.id if approved else None,
            candidate_snapshot_id=None,
            observed_source_sha256=fetched.source_sha256,
            normalized_sha256=None,
            parser_succeeded=False,
            detail=str(error),
        )
        _record_if_requested(client, source, approved, result, check_month, error_summary=str(error))
        return result

    if approved is not None and extracted.normalized_sha256 == approved.normalized_sha256:
        result = MaintenanceResult(
            source_key=source.source_key,
            status="unchanged",
            approved_snapshot_id=approved.id,
            candidate_snapshot_id=None,
            observed_source_sha256=fetched.source_sha256,
            normalized_sha256=extracted.normalized_sha256,
            parser_succeeded=True,
            detail="Raw proficiency file changed but normalized guidance is unchanged",
        )
        _record_if_requested(client, source, approved, result, check_month)
        return result

    parsed = None
    parse_error: str | None = None
    try:
        parsed = parse_alabama_ela_proficiency(source.parser_key, extracted)
    except StandardsIngestError as error:
        parse_error = str(error)

    candidate_id = _stage_snapshot(
        client,
        source=source,
        source_sha256=fetched.source_sha256,
        normalized_sha256=extracted.normalized_sha256,
        resolved_document_url=fetched.resolved_url,
        source_version=resolved.observed_version,
        parser_version=parsed.parser_version if parsed else None,
        parser_succeeded=parsed is not None,
        parser_error=parse_error,
        anchor_text=resolved.anchor_text,
    )

    if parsed is not None:
        _persist_scales(client, candidate_id, parsed.scales)

    result = MaintenanceResult(
        source_key=source.source_key,
        status="changed",
        approved_snapshot_id=approved.id if approved else None,
        candidate_snapshot_id=candidate_id,
        observed_source_sha256=fetched.source_sha256,
        normalized_sha256=extracted.normalized_sha256,
        parser_succeeded=parsed is not None,
        detail=(
            "Current ALSDE proficiency guidance changed and a parsed candidate was staged"
            if parsed is not None
            else "Current ALSDE proficiency guidance changed; candidate requires parser review"
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
    rows = _records(
        _request(
            client,
            "GET",
            "standard_sources",
            params={
                "source_key": f"eq.{source_key}",
                "source_kind": "eq.proficiency_scale",
                "is_active": "eq.true",
                "select": (
                    "id,source_key,landing_url,document_format,resolver_key,parser_key,"
                    "approved_snapshot_id"
                ),
                "limit": "2",
            },
        )
    )
    if len(rows) != 1:
        raise ProficiencyMaintenanceError("Proficiency source is missing or ambiguous")
    row = rows[0]
    return _Source(
        id=_uuid(row, "id"),
        source_key=_text(row, "source_key"),
        landing_url=_text(row, "landing_url"),
        document_format=_text(row, "document_format"),
        resolver_key=_text(row, "resolver_key"),
        parser_key=_text(row, "parser_key"),
        approved_snapshot_id=_optional_uuid(row, "approved_snapshot_id"),
    )


def _load_snapshot(client: SupabaseRestClient, snapshot_id: UUID | None) -> _Snapshot | None:
    if snapshot_id is None:
        return None
    rows = _records(
        _request(
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
    )
    if len(rows) != 1:
        return None
    return _Snapshot(
        id=_uuid(rows[0], "id"),
        source_sha256=_text(rows[0], "source_sha256"),
        normalized_sha256=_text(rows[0], "normalized_sha256"),
    )


def _stage_snapshot(
    client: SupabaseRestClient,
    *,
    source: _Source,
    source_sha256: str,
    normalized_sha256: str,
    resolved_document_url: str,
    source_version: str | None,
    parser_version: str | None,
    parser_succeeded: bool,
    parser_error: str | None,
    anchor_text: str,
) -> UUID:
    existing = _records(
        _request(
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
    )
    provenance: JsonRecord = {
        "landing_url": source.landing_url,
        "anchor_text": anchor_text,
        "resolved_document_url": resolved_document_url,
        "parser_key": source.parser_key,
        "parser_status": "parsed" if parser_succeeded else "failed",
        "source_kind": "proficiency_scale",
        "provides_standard_entries": False,
        "instructional_role": "supplemental_guidance",
    }
    if parser_error:
        provenance["parser_error"] = parser_error

    payload: JsonRecord = {
        "normalized_sha256": normalized_sha256,
        "source_version": source_version,
        "parser_version": parser_version,
        "resolved_document_url": resolved_document_url,
        "provenance": provenance,
    }

    if existing:
        if len(existing) != 1 or _text(existing[0], "status") != "pending":
            raise ProficiencyMaintenanceError(
                "Changed proficiency fingerprint already has a non-pending snapshot"
            )
        snapshot_id = _uuid(existing[0], "id")
        _request(
            client,
            "PATCH",
            "standard_snapshots",
            params={"id": f"eq.{snapshot_id}"},
            payload=payload,
            prefer="return=minimal",
        )
        return snapshot_id

    rows = _records(
        _request(
            client,
            "POST",
            "standard_snapshots",
            payload={
                "source_id": str(source.id),
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
    if len(rows) != 1:
        raise ProficiencyMaintenanceError("Proficiency candidate save returned invalid data")
    return _uuid(rows[0], "id")


def _persist_scales(client: SupabaseRestClient, snapshot_id: UUID, scales: tuple[Any, ...]) -> None:
    _request(
        client,
        "DELETE",
        "standard_proficiency_scales",
        params={"snapshot_id": f"eq.{snapshot_id}"},
        prefer="return=minimal",
    )
    payload = [
        {
            "snapshot_id": str(snapshot_id),
            "grade_band": scale.grade_band,
            "standard_code": scale.standard_code,
            "standard_text": scale.standard_text,
            "literacy_type": scale.literacy_type,
            "focus_area": scale.focus_area,
            "category": scale.category,
            "levels": scale.levels,
        }
        for scale in scales
    ]
    if not payload:
        raise ProficiencyMaintenanceError("Parsed proficiency source produced no scale rows")
    _request(
        client,
        "POST",
        "standard_proficiency_scales",
        payload=payload,
        prefer="return=minimal",
    )


def _update_resolved_url(client: SupabaseRestClient, source_id: UUID, url: str) -> None:
    _request(
        client,
        "PATCH",
        "standard_sources",
        params={"id": f"eq.{source_id}"},
        payload={"document_url": url},
        prefer="return=minimal",
    )


def _record_if_requested(
    client: SupabaseRestClient,
    source: _Source,
    approved: _Snapshot | None,
    result: MaintenanceResult,
    check_month: date | None,
    *,
    error_summary: str | None = None,
) -> None:
    if check_month is None:
        return
    _request(
        client,
        "POST",
        "standard_source_checks",
        params={"on_conflict": "source_id,check_month"},
        payload={
            "source_id": str(source.id),
            "check_month": check_month.replace(day=1).isoformat(),
            "result_status": result.status,
            "approved_snapshot_id_before": str(approved.id) if approved else None,
            "observed_source_sha256": result.observed_source_sha256,
            "candidate_snapshot_id": (
                str(result.candidate_snapshot_id) if result.candidate_snapshot_id else None
            ),
            "resolved_document_url": None,
            "error_summary": error_summary,
            "metadata": {
                "normalized_sha256": result.normalized_sha256,
                "parser_succeeded": result.parser_succeeded,
                "detail": result.detail,
                "source_kind": "proficiency_scale",
            },
        },
        prefer="resolution=merge-duplicates,return=minimal",
    )


def _request(
    client: SupabaseRestClient,
    method: str,
    resource: str,
    *,
    params: dict[str, str] | None = None,
    payload: JsonRecord | list[dict[str, object]] | None = None,
    prefer: str | None = None,
) -> object:
    try:
        return client.request(method, resource, params=params, payload=payload, prefer=prefer)
    except SupabaseRestError as error:
        raise ProficiencyMaintenanceError("Proficiency maintenance database operation failed") from error


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise ProficiencyMaintenanceError("Proficiency maintenance received invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _text(row: JsonRecord, key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProficiencyMaintenanceError(f"Proficiency record is missing {key}")
    return value.strip()


def _uuid(row: JsonRecord, key: str) -> UUID:
    try:
        return UUID(_text(row, key))
    except ValueError as error:
        raise ProficiencyMaintenanceError(f"Proficiency record has invalid {key}") from error


def _optional_uuid(row: JsonRecord, key: str) -> UUID | None:
    value = row.get(key)
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError as error:
        raise ProficiencyMaintenanceError(f"Proficiency record has invalid {key}") from error
