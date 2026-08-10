from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import Any, Literal, cast
from uuid import UUID

from .standards_catalog_discovery import DiscoveredStandardsSource
from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]
DiscoveryState = Literal["unchanged", "changed", "new", "missing"]


class StandardsCatalogReconcileError(RuntimeError):
    """Bounded failure while recording authoritative catalog discovery evidence."""


@dataclass(frozen=True, slots=True)
class CatalogReconcileItem:
    source_key: str
    state: DiscoveryState
    existing_source_id: UUID | None
    discovered: DiscoveredStandardsSource | None
    previous: JsonRecord | None


@dataclass(frozen=True, slots=True)
class CatalogReconcileResult:
    run_id: UUID
    catalog_sha256: str
    items: tuple[CatalogReconcileItem, ...]

    @property
    def unchanged_count(self) -> int:
        return sum(item.state == "unchanged" for item in self.items)

    @property
    def changed_count(self) -> int:
        return sum(item.state == "changed" for item in self.items)

    @property
    def new_count(self) -> int:
        return sum(item.state == "new" for item in self.items)

    @property
    def missing_count(self) -> int:
        return sum(item.state == "missing" for item in self.items)


def reconcile_and_record_catalog(
    client: SupabaseRestClient,
    discovered_sources: tuple[DiscoveredStandardsSource, ...],
    *,
    check_month: date | None = None,
    trigger_kind: Literal["manual", "scheduled"] = "manual",
) -> CatalogReconcileResult:
    existing = _load_existing_alabama_sources(client)
    items = compare_catalog(existing, discovered_sources)
    catalog_hash = catalog_sha256(discovered_sources)

    counts = {
        "unchanged": sum(item.state == "unchanged" for item in items),
        "changed": sum(item.state == "changed" for item in items),
        "new": sum(item.state == "new" for item in items),
        "missing": sum(item.state == "missing" for item in items),
    }
    run_payload: JsonRecord = {
        "check_month": check_month.isoformat() if check_month is not None else None,
        "trigger_kind": trigger_kind,
        "status": "completed",
        "catalog_sha256": catalog_hash,
        "discovered_source_count": len(discovered_sources),
        "unchanged_count": counts["unchanged"],
        "changed_count": counts["changed"],
        "new_count": counts["new"],
        "missing_count": counts["missing"],
        "metadata": {
            "contract": "catalog-discovery-v1",
            "mutates_approved_sources": False,
        },
    }
    try:
        run_rows = _records(
            client.request(
                "POST",
                "standard_catalog_discovery_runs",
                payload=run_payload,
                prefer="return=representation",
            )
        )
    except SupabaseRestError as error:
        raise StandardsCatalogReconcileError(
            "Standards catalog discovery run could not be recorded"
        ) from error
    if len(run_rows) != 1:
        raise StandardsCatalogReconcileError(
            "Standards catalog discovery run returned invalid data"
        )
    run_id = _required_uuid(run_rows[0], "id")

    item_payloads = [_item_payload(run_id, item) for item in items]
    if item_payloads:
        try:
            client.request(
                "POST",
                "standard_catalog_discovery_items",
                payload=item_payloads,
                prefer="return=minimal",
            )
        except SupabaseRestError as error:
            _mark_catalog_run_error(
                client,
                run_id,
                "Standards catalog discovery items could not be recorded",
            )
            raise StandardsCatalogReconcileError(
                "Standards catalog discovery items could not be recorded"
            ) from error

    return CatalogReconcileResult(
        run_id=run_id,
        catalog_sha256=catalog_hash,
        items=items,
    )


def _mark_catalog_run_error(
    client: SupabaseRestClient,
    run_id: UUID,
    detail: str,
) -> None:
    """Best-effort correction when a run header exists but its evidence batch fails."""
    try:
        client.request(
            "PATCH",
            "standard_catalog_discovery_runs",
            params={"id": f"eq.{run_id}"},
            payload={"status": "error", "error_summary": detail},
            prefer="return=minimal",
        )
    except SupabaseRestError:
        # Preserve the original reconciliation failure as the primary error. A later governed
        # audit repair can identify a completed run with no item evidence deterministically.
        return


def compare_catalog(
    existing_sources: tuple[JsonRecord, ...],
    discovered_sources: tuple[DiscoveredStandardsSource, ...],
) -> tuple[CatalogReconcileItem, ...]:
    existing_by_key = {
        _required_text(record, "source_key"): record
        for record in existing_sources
        if _is_alabama_source(record)
    }
    discovered_by_key = {source.source_key: source for source in discovered_sources}
    keys = sorted(set(existing_by_key) | set(discovered_by_key))
    items: list[CatalogReconcileItem] = []

    for source_key in keys:
        previous = existing_by_key.get(source_key)
        discovered = discovered_by_key.get(source_key)
        if previous is None and discovered is not None:
            state: DiscoveryState = "new"
            existing_id = None
        elif previous is not None and discovered is None:
            state = "missing"
            existing_id = _required_uuid(previous, "id")
        elif previous is not None and discovered is not None:
            state = "unchanged" if _descriptor_matches(previous, discovered) else "changed"
            existing_id = _required_uuid(previous, "id")
        else:  # pragma: no cover - impossible because key is from the union.
            continue

        items.append(
            CatalogReconcileItem(
                source_key=source_key,
                state=state,
                existing_source_id=existing_id,
                discovered=discovered,
                previous=previous,
            )
        )

    return tuple(items)


def catalog_sha256(
    discovered_sources: tuple[DiscoveredStandardsSource, ...],
) -> str:
    normalized = [
        {
            "source_key": source.source_key,
            "family": source.family,
            "category_key": source.category_key,
            "category_name": source.category_name,
            "category_type": source.category_type,
            "authority": source.authority,
            "title": source.title,
            "edition": source.edition,
            "landing_url": source.landing_url,
            "document_url": source.document_url,
            "document_format": source.document_format,
            "parser_key_hint": source.parser_key_hint,
            "source_kind": source.source_kind,
        }
        for source in sorted(discovered_sources, key=lambda item: item.source_key)
    ]
    serialized = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def _load_existing_alabama_sources(
    client: SupabaseRestClient,
) -> tuple[JsonRecord, ...]:
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_sources",
                params={
                    "select": (
                        "id,source_key,family,authority,title,edition,landing_url,document_url,"
                        "document_format,parser_key,catalog_category_key,catalog_category_name,"
                        "catalog_category_type,discovery_status,is_active"
                    ),
                    "order": "source_key.asc",
                },
            )
        )
    except SupabaseRestError as error:
        raise StandardsCatalogReconcileError(
            "Existing standards catalog could not be loaded"
        ) from error
    return tuple(record for record in rows if _is_alabama_source(record))


def _is_alabama_source(record: JsonRecord) -> bool:
    family = record.get("family")
    authority = record.get("authority")
    return (
        isinstance(family, str)
        and family.startswith("alabama_")
        and authority == "Alabama State Department of Education"
    )


def _descriptor_matches(
    previous: JsonRecord,
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
    return all(previous.get(key) == value for key, value in expected.items())


def _item_payload(run_id: UUID, item: CatalogReconcileItem) -> JsonRecord:
    discovered = item.discovered
    previous = item.previous or {}
    return {
        "run_id": str(run_id),
        "source_key": item.source_key,
        "result_state": item.state,
        "existing_source_id": (
            str(item.existing_source_id) if item.existing_source_id is not None else None
        ),
        "family": (
            discovered.family
            if discovered is not None
            else _required_text(previous, "family")
        ),
        "category_key": (
            discovered.category_key
            if discovered is not None
            else _optional_text(previous, "catalog_category_key")
        ),
        "category_name": (
            discovered.category_name
            if discovered is not None
            else _optional_text(previous, "catalog_category_name")
        ),
        "category_type": (
            discovered.category_type
            if discovered is not None
            else _optional_text(previous, "catalog_category_type")
        ),
        "authority": (
            discovered.authority
            if discovered is not None
            else _required_text(previous, "authority")
        ),
        "observed_title": discovered.title if discovered is not None else None,
        "observed_edition": discovered.edition if discovered is not None else None,
        "observed_landing_url": discovered.landing_url if discovered is not None else None,
        "observed_document_url": discovered.document_url if discovered is not None else None,
        "observed_document_format": (
            discovered.document_format if discovered is not None else None
        ),
        "parser_key_hint": discovered.parser_key_hint if discovered is not None else None,
        "source_kind": discovered.source_kind if discovered is not None else None,
        "previous_title": _optional_text(previous, "title"),
        "previous_edition": _optional_text(previous, "edition"),
        "previous_document_url": _optional_text(previous, "document_url"),
        "metadata": {"automatic_activation": False},
    }


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise StandardsCatalogReconcileError(
            "Standards catalog persistence returned invalid data"
        )
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _required_text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StandardsCatalogReconcileError(
            f"Standards catalog record is missing {key}"
        )
    return value.strip()


def _optional_text(record: JsonRecord, key: str) -> str | None:
    value = record.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _required_uuid(record: JsonRecord, key: str) -> UUID:
    try:
        return UUID(_required_text(record, key))
    except ValueError as error:
        raise StandardsCatalogReconcileError(
            f"Standards catalog record has invalid {key}"
        ) from error
