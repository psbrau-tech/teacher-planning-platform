from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from app.settings import Settings
from app.standards_maintenance import (
    MaintenanceResult,
    StandardsMaintenanceError,
    service_role_client,
)
from app.standards_monthly_run import (
    StandardsReconciliationRunError,
    StandardsReconciliationRunResult,
    run_standards_reconciliation,
)
from app.standards_parser_rematerialization import stage_parser_rematerialization_if_needed
from app.standards_schedule import scheduled_reconciliation_kind


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("dates must use YYYY-MM-DD") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile the governed Alabama standards catalog using annual full, "
            "quarterly lightweight, event-driven, or controlled manual maintenance."
        )
    )
    parser.add_argument(
        "--kind",
        choices=("annual_full", "quarterly_monitor", "event_driven", "manual"),
        default="manual",
        help="Reconciliation scope. Scheduled runs resolve this automatically when requested.",
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help=(
            "Affected source key. Repeat as needed. Required for event-driven runs; "
            "optional for controlled manual runs."
        ),
    )
    parser.add_argument(
        "--check-date",
        type=_date,
        help="Evidence date. Defaults to today.",
    )
    parser.add_argument(
        "--scheduled-only",
        action="store_true",
        help=(
            "Resolve the due annual/quarterly reconciliation from --check-date and no-op "
            "when neither scheduled layer is due."
        ),
    )
    parser.add_argument(
        "--non-working-date",
        action="append",
        type=_date,
        default=[],
        help="Explicit business-day exclusion used when resolving the first workday.",
    )
    return parser


def _result_payload(result: MaintenanceResult) -> dict[str, object]:
    return {
        "source_key": result.source_key,
        "status": result.status,
        "approved_snapshot_id": (
            str(result.approved_snapshot_id) if result.approved_snapshot_id else None
        ),
        "candidate_snapshot_id": (
            str(result.candidate_snapshot_id) if result.candidate_snapshot_id else None
        ),
        "parser_succeeded": result.parser_succeeded,
        "detail": result.detail,
    }


def _catalog_payload(result: StandardsReconciliationRunResult) -> dict[str, object]:
    catalog = result.catalog_result
    return {
        "status": "unavailable_error" if result.catalog_error else "checked",
        "run_id": (
            str(catalog.run_id)
            if catalog is not None
            else str(result.catalog_error_run_id)
            if result.catalog_error_run_id is not None
            else None
        ),
        "catalog_sha256": catalog.catalog_sha256 if catalog is not None else None,
        "unchanged_count": catalog.unchanged_count if catalog is not None else 0,
        "changed_count": catalog.changed_count if catalog is not None else 0,
        "new_count": catalog.new_count if catalog is not None else 0,
        "missing_count": catalog.missing_count if catalog is not None else 0,
        "error": result.catalog_error,
    }


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    check_date: date = args.check_date or date.today()
    non_working_dates = frozenset(args.non_working_date)
    reconciliation_kind = args.kind
    trigger_kind = "manual"

    if args.scheduled_only:
        due_kind = scheduled_reconciliation_kind(
            check_date,
            non_working_dates=non_working_dates,
        )
        if due_kind is None:
            print(
                json.dumps(
                    {
                        "status": "not_due",
                        "check_date": check_date.isoformat(),
                    },
                    sort_keys=True,
                )
            )
            return 0
        reconciliation_kind = due_kind
        trigger_kind = "scheduled"

    if reconciliation_kind == "event_driven" and not args.sources:
        raise StandardsReconciliationRunError(
            "Event-driven reconciliation requires one or more --source values"
        )

    settings = Settings()
    client = service_role_client(settings)
    result = run_standards_reconciliation(
        client,
        check_date=check_date,
        reconciliation_kind=reconciliation_kind,
        trigger_kind=trigger_kind,
        source_keys=tuple(args.sources) if args.sources else None,
    )

    parser_rematerializations: list[MaintenanceResult] = []
    for source_result in result.source_results:
        rematerialization = stage_parser_rematerialization_if_needed(
            client,
            source_result.source_key,
            check_date=check_date,
        )
        if rematerialization is not None:
            parser_rematerializations.append(rematerialization)

    requires_review = result.requires_review or bool(parser_rematerializations)

    print(
        json.dumps(
            {
                "check_date": check_date.isoformat(),
                "trigger_kind": trigger_kind,
                "reconciliation_kind": reconciliation_kind,
                "catalog": _catalog_payload(result),
                "sources": [_result_payload(item) for item in result.source_results],
                "parser_rematerializations": [
                    _result_payload(item) for item in parser_rematerializations
                ],
                "requires_review": requires_review,
                "has_unavailable_error": result.has_unavailable_error,
            },
            sort_keys=True,
        )
    )

    if result.has_unavailable_error:
        return 2
    if requires_review:
        return 3
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (StandardsReconciliationRunError, StandardsMaintenanceError) as error:
        print(
            json.dumps(
                {
                    "status": "maintenance_error",
                    "detail": str(error),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from error
