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
    stage_authoritative_source,
)
from app.standards_schedule import monthly_check_is_due

DEFAULT_SOURCE_KEYS = (
    "alabama_ela_2021",
    "alabama_bma_2021",
    "army_jrotc_v12",
)


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("dates must use YYYY-MM-DD") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage or validate governed authoritative standards sources."
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help=(
            "Source key to process. Repeat for multiple sources; default processes "
            "all pilot sources."
        ),
    )
    parser.add_argument(
        "--check-date",
        type=_date,
        help=(
            "Record a monthly source check for the month containing this date. "
            "Without this option, stage/compare without creating monthly evidence."
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


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    check_date: date | None = args.check_date
    non_working_dates = frozenset(args.non_working_date)

    if args.first_workday_only:
        if check_date is None:
            raise StandardsMaintenanceError(
                "--first-workday-only requires --check-date"
            )
        if not monthly_check_is_due(
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
    source_keys = tuple(args.sources or DEFAULT_SOURCE_KEYS)
    results = [
        stage_authoritative_source(
            client,
            source_key,
            check_month=check_date,
        )
        for source_key in source_keys
    ]

    print(
        json.dumps(
            {
                "check_date": check_date.isoformat() if check_date else None,
                "results": [_result_payload(result) for result in results],
            },
            sort_keys=True,
        )
    )

    if any(result.status == "unavailable_error" for result in results):
        return 2
    if any(result.status == "changed" for result in results):
        return 3
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except StandardsMaintenanceError as error:
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
