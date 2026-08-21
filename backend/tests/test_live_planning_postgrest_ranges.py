from datetime import date
from pathlib import Path

from app.live_planning_api import _date_range_filter


def test_date_range_filter_uses_top_level_postgrest_predicates() -> None:
    assert _date_range_filter(
        "school_date",
        date(2026, 8, 10),
        date(2026, 8, 14),
    ) == "(school_date.gte.2026-08-10,school_date.lte.2026-08-14)"

    assert _date_range_filter(
        "exception_date",
        date(2026, 8, 10),
        date(2026, 8, 14),
    ) == "(exception_date.gte.2026-08-10,exception_date.lte.2026-08-14)"


def test_live_planning_has_no_column_level_and_range_filters() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "app" / "live_planning_api.py"
    ).read_text(encoding="utf-8")

    assert "and(gte." not in source
    assert source.count('"and": _date_range_filter') == 5
    assert '"is_teacher_override": "eq.true"' in source
