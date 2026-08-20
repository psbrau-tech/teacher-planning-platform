from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

from .standards_catalog_audit import (
    StandardsCatalogAuditError,
    record_catalog_discovery_error,
)
from .standards_catalog_discovery import StandardsCatalogDiscoveryError
from .standards_catalog_fetch import fetch_current_alabama_catalog
from .standards_catalog_materialize import (
    CatalogMaterializeError,
    materialize_discovered_source,
)
from .standards_catalog_reconcile import (
    CatalogReconcileResult,
    StandardsCatalogReconcileError,
    reconcile_and_record_catalog,
)
from .standards_governed_sources import (
    GovernedStandardsSourceError,
    list_governed_source_keys,
)
from .standards_governed_validation import (
    GovernedStandardsValidationError,
    validate_governed_source,
)
from .standards_maintenance import MaintenanceResult
from .standards_proficiency_maintenance import (
    ProficiencyMaintenanceError,
    is_proficiency_source_key,
    proficiency_source_keys,
    validate_proficiency_source,
)
from .supabase_rest import SupabaseRestClient

ReconciliationKind = Literal["annual_full", "quarterly_monitor", "event_driven", "manual"]
TriggerKind = Literal["manual", "scheduled"]


class StandardsReconciliationRunError(RuntimeError):
    """Bounded failure in governed standards-reconciliation orchestration."""


# Compatibility alias while Gate E callers migrate away from monthly terminology.
StandardsMonthlyRunError = StandardsReconciliationRunError


@dataclass(frozen=True, slots=True)
class StandardsReconciliationRunResult:
    check_date: date
    trigger_kind: TriggerKind
    reconciliation_kind: ReconciliationKind
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


# Compatibility alias for existing imports/tests until the module is renamed in a later cleanup.
MonthlyStandardsRunResult = StandardsReconciliationRunResult


def _materialize_annual_catalog_candidates(
    client: SupabaseRestClient,
    catalog_result: CatalogReconcileResult,
) -> None:
    """Stage current changed/new catalog sources without approving or activating them."""
    for item in catalog_result.items:
        if item.state not in {"new", "changed"} or item.discovered is None:
            continue
        try:
            materialize_discovered_source(client, item.discovered)
        except CatalogMaterializeError as error:
            raise StandardsReconciliationRunError(
                f"Discovered standards source could not be staged: {item.source_key}"
            ) from error


def _validate_source_keys(
    client: SupabaseRestClient,
    source_keys: tuple[str, ...],
    *,
    check_date: date,
) -> tuple[MaintenanceResult, ...]:
    results: list[MaintenanceResult] = []
    for source_key in source_keys:
        try:
            if is_proficiency_source_key(source_key):
                results.append(
                    validate_proficiency_source(
                        client,
                        source_key,
                        check_month=check_date,
                    )
                )
            else:
                results.append(
                    validate_governed_source(
                        client,
                        source_key,
                        check_month=check_date,
                    )
                )
        except (GovernedStandardsValidationError, ProficiencyMaintenanceError) as error:
            raise StandardsReconciliationRunError(
                f"Governed standards source could not be validated: {source_key}"
            ) from error
    return tuple(results)


def run_standards_reconciliation(
    client: SupabaseRestClient,
    *,
    check_date: date,
    reconciliation_kind: ReconciliationKind,
    trigger_kind: TriggerKind = "scheduled",
    source_keys: tuple[str, ...] | None = None,
) -> StandardsReconciliationRunResult:
    """Run catalog monitoring and governed source validation.

    Quarterly monitoring keeps the catalog metadata check lightweight while also validating
    the seven current ALSDE Grade 6-12 ELA proficiency-scale sources. July's annual full
    validation replaces that quarter and validates every governed source. Event-driven and
    manual reconciliation may target either authoritative standards or proficiency guidance.
    """
    if reconciliation_kind == "event_driven" and not source_keys:
        raise StandardsReconciliationRunError(
            "Event-driven standards reconciliation requires at least one affected source"
        )

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
        try:
            catalog_error_run_id = record_catalog_discovery_error(
                client,
                detail=catalog_error,
                check_month=check_date,
                trigger_kind=trigger_kind,
            )
        except StandardsCatalogAuditError as audit_error:
            raise StandardsReconciliationRunError(
                "Catalog discovery failed and its audit record could not be saved"
            ) from audit_error
    except StandardsCatalogReconcileError as error:
        raise StandardsReconciliationRunError(
            "Authoritative standards catalog reconciliation failed"
        ) from error

    if reconciliation_kind == "annual_full" and catalog_result is not None:
        _materialize_annual_catalog_candidates(client, catalog_result)

    if reconciliation_kind == "quarterly_monitor":
        source_results = _validate_source_keys(
            client,
            proficiency_source_keys(),
            check_date=check_date,
        )
        return StandardsReconciliationRunResult(
            check_date=check_date,
            trigger_kind=trigger_kind,
            reconciliation_kind=reconciliation_kind,
            catalog_result=catalog_result,
            catalog_error_run_id=catalog_error_run_id,
            catalog_error=catalog_error,
            source_results=source_results,
        )

    try:
        governed_keys = (
            source_keys if source_keys is not None else list_governed_source_keys(client)
        )
    except GovernedStandardsSourceError as error:
        raise StandardsReconciliationRunError(
            "Governed standards source list could not be loaded"
        ) from error
    if not governed_keys:
        raise StandardsReconciliationRunError("No governed standards sources are configured")

    source_results = _validate_source_keys(
        client,
        tuple(governed_keys),
        check_date=check_date,
    )

    return StandardsReconciliationRunResult(
        check_date=check_date,
        trigger_kind=trigger_kind,
        reconciliation_kind=reconciliation_kind,
        catalog_result=catalog_result,
        catalog_error_run_id=catalog_error_run_id,
        catalog_error=catalog_error,
        source_results=source_results,
    )


def run_monthly_standards_validation(
    client: SupabaseRestClient,
    *,
    check_date: date,
    trigger_kind: TriggerKind = "scheduled",
    source_keys: tuple[str, ...] | None = None,
) -> StandardsReconciliationRunResult:
    """Deprecated compatibility wrapper: perform a full governed validation.

    New scheduling code must call ``run_standards_reconciliation`` with an explicit
    reconciliation kind so quarterly monitoring remains bounded.
    """
    return run_standards_reconciliation(
        client,
        check_date=check_date,
        reconciliation_kind="annual_full",
        trigger_kind=trigger_kind,
        source_keys=source_keys,
    )
