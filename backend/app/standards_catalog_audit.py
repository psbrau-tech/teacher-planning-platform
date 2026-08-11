from __future__ import annotations

from datetime import date
from hashlib import sha256
from typing import Any, Literal, cast
from uuid import UUID

from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]


class StandardsCatalogAuditError(RuntimeError):
    """Bounded failure while recording a catalog-level discovery failure."""


def record_catalog_discovery_error(
    client: SupabaseRestClient,
    *,
    detail: str,
    check_month: date | None,
    trigger_kind: Literal["manual", "scheduled"],
) -> UUID:
    error_summary = detail.strip() or "Authoritative Alabama standards catalog is unavailable"
    catalog_hash = sha256(b"alabama-catalog-unavailable").hexdigest()
    payload: JsonRecord = {
        "check_month": check_month.isoformat() if check_month is not None else None,
        "trigger_kind": trigger_kind,
        "status": "error",
        "catalog_sha256": catalog_hash,
        "discovered_source_count": 0,
        "unchanged_count": 0,
        "changed_count": 0,
        "new_count": 0,
        "missing_count": 0,
        "error_summary": error_summary[:1000],
        "metadata": {
            "phase": "catalog_fetch_or_parse",
            "approved_sources_remain_active": True,
        },
    }
    try:
        result = client.request(
            "POST",
            "standard_catalog_discovery_runs",
            payload=payload,
            prefer="return=representation",
        )
    except SupabaseRestError as error:
        raise StandardsCatalogAuditError(
            "Standards catalog failure evidence could not be recorded"
        ) from error
    if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
        raise StandardsCatalogAuditError(
            "Standards catalog failure evidence returned invalid data"
        )
    record = cast(JsonRecord, result[0])
    value = record.get("id")
    try:
        return UUID(str(value))
    except ValueError as error:
        raise StandardsCatalogAuditError(
            "Standards catalog failure evidence returned an invalid identifier"
        ) from error
