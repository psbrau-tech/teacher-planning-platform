from datetime import date

import pytest

from app.standards_schedule import (
    StandardsScheduleError,
    first_workday,
    monthly_check_is_due,
)


def test_first_workday_returns_first_weekday_when_available() -> None:
    assert first_workday(2026, 9) == date(2026, 9, 1)


def test_first_workday_rolls_weekend_to_monday() -> None:
    assert first_workday(2026, 8) == date(2026, 8, 3)


def test_first_workday_honors_explicit_non_working_dates() -> None:
    non_working = frozenset({date(2027, 1, 1)})

    assert first_workday(2027, 1, non_working_dates=non_working) == date(2027, 1, 4)


def test_monthly_check_is_due_only_on_resolved_first_workday() -> None:
    non_working = frozenset({date(2027, 1, 1)})

    assert not monthly_check_is_due(date(2027, 1, 1), non_working_dates=non_working)
    assert not monthly_check_is_due(date(2027, 1, 3), non_working_dates=non_working)
    assert monthly_check_is_due(date(2027, 1, 4), non_working_dates=non_working)
    assert not monthly_check_is_due(date(2027, 1, 5), non_working_dates=non_working)


def test_first_workday_rejects_invalid_month() -> None:
    with pytest.raises(StandardsScheduleError, match="month must be between 1 and 12"):
        first_workday(2026, 13)
