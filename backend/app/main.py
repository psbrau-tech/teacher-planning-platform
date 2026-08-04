from datetime import date

from fastapi import FastAPI, HTTPException, Query

from .fixtures import (
    ASSIGNMENT_IDS,
    afternoon_block_pattern,
    anniston_exceptions,
    period_pattern,
    synthetic_jrotc_lessons,
)
from .models import PlannedLesson
from .planner import build_weekly_plan

app = FastAPI(
    title="Teacher Planning Platform API",
    version="0.1.0",
    description="Version 1 pilot API for Anniston City Schools.",
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tpp-api"}


@app.get("/api/v1/assignments", tags=["teacher"])
def list_assignments() -> list[dict[str, object]]:
    """Synthetic pilot endpoint until Supabase persistence is connected."""
    return [
        {
            "id": assignment_id,
            "course_name": level,
            "schedule_type": "block" if level == "LET 4" else "period",
            "curriculum": f"Army JROTC {level}",
        }
        for level, assignment_id in ASSIGNMENT_IDS.items()
    ]


@app.get("/api/v1/weekly-plan", response_model=list[PlannedLesson], tags=["planning"])
def weekly_plan(
    level: str = Query(pattern=r"^LET [1-4]$"),
    week_start: date = Query(description="Monday date for the requested week"),
) -> list[PlannedLesson]:
    assignment_id = ASSIGNMENT_IDS.get(level)
    if assignment_id is None:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")

    patterns = [afternoon_block_pattern()] if level == "LET 4" else [period_pattern()]
    return build_weekly_plan(
        assignment_id=assignment_id,
        week_start=week_start,
        patterns=patterns,
        lessons=synthetic_jrotc_lessons(level),
        exceptions=anniston_exceptions(),
    )
