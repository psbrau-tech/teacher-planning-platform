from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from .auth import AuthenticatedTeacher, require_teacher
from .notifications_api import router as notifications_router
from .reflection_intelligence_api import router as reflection_intelligence_router

# Keep the historical AI-reflection assistance route fail-closed while registering the separate
# Reflection Intelligence and notification surfaces. Reflection Intelligence analyzes explicitly
# submitted teacher-authored reflections; it never creates or rewrites the 12 required responses.
router = APIRouter()
reflection_assistance_router = APIRouter(prefix="/api/v1/ai", tags=["ai-reflection"])


@reflection_assistance_router.post("/reflection/{assignment_id}/week/{week_start}")
def suggest_weekly_reflection_disabled(
    assignment_id: UUID,
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
) -> None:
    """Fail closed: the district reflection is intentionally teacher-authored only."""
    del assignment_id, week_start, identity
    raise HTTPException(
        status_code=410,
        detail=(
            "AI reflection assistance is disabled. Weekly Reflection / PLC Discussion "
            "must be authored by the teacher."
        ),
    )


router.include_router(reflection_assistance_router)
router.include_router(reflection_intelligence_router)
router.include_router(notifications_router)
