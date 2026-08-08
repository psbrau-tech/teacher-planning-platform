from __future__ import annotations

from datetime import date, timedelta

ANNUAL_FULL_VALIDATION_MONTH = 7
QUARTERLY_MONITOR_MONTHS = frozenset({1, 4, 10})


class StandardsScheduleError(ValueError):
    """Invalid standards-reconciliation scheduling input."""


def first_workday(
    year: int,
    month: int,
    *,
    non_working_dates: frozenset[date] = frozenset(),
) -> date:
    if month < 1 or month > 12:
        raise StandardsScheduleError("month must be between 1 and 12")

    candidate = date(year, month, 1)
    while candidate.month == month:
        if candidate.weekday() < 5 and candidate not in non_working_dates:
            return candidate
        candidate += timedelta(days=1)
    raise StandardsScheduleError("month contains no eligible workday")


def annual_full_validation_is_due(
    today: date,
    *,
    validation_month: int = ANNUAL_FULL_VALIDATION_MONTH,
    non_working_dates: frozenset[date] = frozenset(),
) -> bool:
    """Return True on the first eligible workday of the annual validation month."""
    return today == first_workday(
        today.year,
        validation_month,
        non_working_dates=non_working_dates,
    )


def quarterly_monitor_is_due(
    today: date,
    *,
    monitor_months: frozenset[int] = QUARTERLY_MONITOR_MONTHS,
    non_working_dates: frozenset[date] = frozenset(),
) -> bool:
    """Return True for lightweight catalog monitoring in configured quarter months.

    July is intentionally omitted from the default quarterly cadence because the annual
    full-catalog/source validation replaces that quarter's lightweight monitor.
    """
    if today.month not in monitor_months:
        return False
    return today == first_workday(
        today.year,
        today.month,
        non_working_dates=non_working_dates,
    )


def scheduled_reconciliation_kind(
    today: date,
    *,
    validation_month: int = ANNUAL_FULL_VALIDATION_MONTH,
    monitor_months: frozenset[int] = QUARTERLY_MONITOR_MONTHS,
    non_working_dates: frozenset[date] = frozenset(),
) -> str | None:
    if annual_full_validation_is_due(
        today,
        validation_month=validation_month,
        non_working_dates=non_working_dates,
    ):
        return "annual_full"
    if quarterly_monitor_is_due(
        today,
        monitor_months=monitor_months,
        non_working_dates=non_working_dates,
    ):
        return "quarterly_monitor"
    return None
