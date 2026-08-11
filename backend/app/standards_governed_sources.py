from __future__ import annotations

from typing import Any, cast

from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]


class GovernedStandardsSourceError(RuntimeError):
    """Bounded failure while listing standards sources eligible for maintenance."""


def list_governed_source_keys(client: SupabaseRestClient) -> tuple[str, ...]:
    try:
        payload = client.request(
            "GET",
            "standard_sources",
            params={
                "is_active": "eq.true",
                "discovery_status": "eq.approved",
                "select": "source_key",
                "order": "source_key.asc",
            },
        )
    except SupabaseRestError as error:
        raise GovernedStandardsSourceError(
            "Governed standards sources could not be loaded"
        ) from error

    if not isinstance(payload, list):
        raise GovernedStandardsSourceError(
            "Governed standards source list returned invalid data"
        )

    keys: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        record = cast(JsonRecord, item)
        value = record.get("source_key")
        if not isinstance(value, str) or not value.strip():
            raise GovernedStandardsSourceError(
                "Governed standards source list contains an invalid key"
            )
        keys.append(value.strip())
    return tuple(keys)
