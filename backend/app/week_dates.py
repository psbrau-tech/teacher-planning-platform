from __future__ import annotations

from datetime import date

from fastapi import HTTPException


def require_monday(value: date) -> date:
    """Enforce the canonical Monday week-start invariant at API boundaries."""
    if value.weekday() != 0:
        raise HTTPException(
            status_code=422,
            detail=(
                "Week of must be a Monday. Choose the Monday that starts the intended planning week."
            ),
        )
    return value
