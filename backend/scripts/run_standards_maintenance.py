from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from app.settings import Settings
from app.standards_maintenance import MaintenanceResult, StandardsMaintenanceError, service_role_client
from app.standards_monthly_run import (
    MonthlyStandardsRunResult,
    StandardsMonthlyRunError,
    run_monthly_standards_validation,
)
from app.standards_schedule import monthly_check_is_due


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("dates must use YYYY-MM-DD") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover the current Alabama standards catalog and validate every governed "
            "authoritative standards source."
        )
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help=(
            "Optional source key to validate. Repeat to restrict source-content checks; "
            "Alabama catalog discovery still evaluates the complete authoritative catalog."
        ),
    )
    parser.add_argument(
        "--check-date",
        type=_date,
        help=(
            "Date used for monthly evidence. Defaults to today for a manual run. "
            "Monthly source evidence is safely upserted for retries."
        ),
    )
    parser.add_argument(
        "--first-workday-only",
        action="store_true",
        help="No-op unless --check-date is the resolved first workday of its month.",
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


def _catalog_payload(result: MonthlyStandardsRunResult) -> dict[str, object]:
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

    if args.first_workday_only and not monthly_check_is_due(
        check_date,
        non_working_dates=non_working_dates,
    ):
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

    settings = Settings()
    client = service_role_client(settings)
    trigger_kind = "scheduled" if args.first_workday_only else "manual"
    result = run_monthly_standards_validation(
        client,
        check_date=check_date,
        trigger_kind=trigger_kind,
        source_keys=tuple(args.sources) if args.sources else None,
    )

    print(
        json.dumps(
            {
                "check_date": check_date.isoformat(),
                "trigger_kind": trigger_kind,
                "catalog": _catalog_payload(result),
                "sources": [_result_payload(item) for item in result.source_results],
                "requires_review": result.requires_review,
                "has_unavailable_error": result.has_unavailable_error,
            },
            sort_keys=True,
        )
    )

    if result.has_unavailable_error:
        return 2
    if result.requires_review:
        return 3
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (StandardsMaintenanceError, StandardsMonthlyRunError) as error:
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
