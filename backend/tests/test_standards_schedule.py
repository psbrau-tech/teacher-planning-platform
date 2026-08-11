from datetime import date

import pytest

from app.standards_schedule import (
    StandardsScheduleError,
    annual_full_validation_is_due,
    first_workday,
    quarterly_monitor_is_due,
    scheduled_reconciliation_kind,
)


def test_first_workday_returns_first_weekday_when_available() -> None:
    assert first_workday(2026, 9) == date(2026, 9, 1)


def test_first_workday_rolls_weekend_to_monday() -> None:
    assert first_workday(2026, 8) == date(2026, 8, 3)


def test_first_workday_honors_explicit_non_working_dates() -> None:
    non_working = frozenset({date(2027, 1, 1)})

    assert first_workday(2027, 1, non_working_dates=non_working) == date(2027, 1, 4)


def test_annual_full_validation_defaults_to_first_workday_of_july() -> None:
    assert annual_full_validation_is_due(date(2027, 7, 1))
    assert not annual_full_validation_is_due(date(2027, 7, 2))
    assert not annual_full_validation_is_due(date(2027, 8, 2))


def test_annual_full_validation_honors_school_non_working_dates() -> None:
    non_working = frozenset({date(2027, 7, 1), date(2027, 7, 2)})

    assert not annual_full_validation_is_due(
        date(2027, 7, 2), non_working_dates=non_working
    )
    assert annual_full_validation_is_due(
        date(2027, 7, 5), non_working_dates=non_working
    )


def test_quarterly_monitor_runs_january_april_and_october_but_not_july() -> None:
    assert quarterly_monitor_is_due(date(2027, 1, 1))
    assert quarterly_monitor_is_due(date(2027, 4, 1))
    assert quarterly_monitor_is_due(date(2027, 10, 1))
    assert not quarterly_monitor_is_due(date(2027, 7, 1))


def test_scheduled_kind_prioritizes_annual_full_validation() -> None:
    assert scheduled_reconciliation_kind(date(2027, 7, 1)) == "annual_full"
    assert scheduled_reconciliation_kind(date(2027, 10, 1)) == "quarterly_monitor"
    assert scheduled_reconciliation_kind(date(2027, 11, 1)) is None


def test_first_workday_rejects_invalid_month() -> None:
    with pytest.raises(StandardsScheduleError, match="month must be between 1 and 12"):
        first_workday(2026, 13)
