from __future__ import annotations

from datetime import date, timedelta


class StandardsScheduleError(ValueError):
    """Invalid monthly standards-maintenance scheduling input."""


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


def monthly_check_is_due(
    today: date,
    *,
    non_working_dates: frozenset[date] = frozenset(),
) -> bool:
    return today == first_workday(
        today.year,
        today.month,
        non_working_dates=non_working_dates,
    )
