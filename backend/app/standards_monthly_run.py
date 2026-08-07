from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

from .standards_catalog_audit import record_catalog_discovery_error
from .standards_catalog_discovery import StandardsCatalogDiscoveryError
from .standards_catalog_fetch import fetch_current_alabama_catalog
from .standards_catalog_reconcile import (
    CatalogReconcileResult,
    reconcile_and_record_catalog,
)
from .standards_governed_sources import list_governed_source_keys
from .standards_maintenance import MaintenanceResult, stage_authoritative_source
from .supabase_rest import SupabaseRestClient


class StandardsMonthlyRunError(RuntimeError):
    """Bounded failure in the complete monthly standards-validation orchestration."""


@dataclass(frozen=True, slots=True)
class MonthlyStandardsRunResult:
    check_date: date
    trigger_kind: Literal["manual", "scheduled"]
    catalog_result: CatalogReconcileResult | None
    catalog_error_run_id: UUID | None
    catalog_error: str | None
    source_results: tuple[MaintenanceResult, ...]

    @property
    def requires_review(self) -> bool:
        if self.catalog_result is not None and (
            self.catalog_result.changed_count > 0
            or self.catalog_result.new_count > 0
            or self.catalog_result.missing_count > 0
        ):
            return True
        return any(result.status == "changed" for result in self.source_results)

    @property
    def has_unavailable_error(self) -> bool:
        return self.catalog_error is not None or any(
            result.status == "unavailable_error" for result in self.source_results
        )


def run_monthly_standards_validation(
    client: SupabaseRestClient,
    *,
    check_date: date,
    trigger_kind: Literal["manual", "scheduled"] = "scheduled",
    source_keys: tuple[str, ...] | None = None,
) -> MonthlyStandardsRunResult:
    catalog_result: CatalogReconcileResult | None = None
    catalog_error_run_id: UUID | None = None
    catalog_error: str | None = None

    try:
        discovered = fetch_current_alabama_catalog()
        catalog_result = reconcile_and_record_catalog(
            client,
            discovered,
            check_month=check_date,
            trigger_kind=trigger_kind,
        )
    except StandardsCatalogDiscoveryError as error:
        catalog_error = str(error)
        catalog_error_run_id = record_catalog_discovery_error(
            client,
            detail=catalog_error,
            check_month=check_date,
            trigger_kind=trigger_kind,
        )

    governed_keys = source_keys if source_keys is not None else list_governed_source_keys(client)
    if not governed_keys:
        raise StandardsMonthlyRunError("No governed standards sources are configured")

    source_results = tuple(
        stage_authoritative_source(
            client,
            source_key,
            check_month=check_date,
        )
        for source_key in governed_keys
    )
    return MonthlyStandardsRunResult(
        check_date=check_date,
        trigger_kind=trigger_kind,
        catalog_result=catalog_result,
        catalog_error_run_id=catalog_error_run_id,
        catalog_error=catalog_error,
        source_results=source_results,
    )
