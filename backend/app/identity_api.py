from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import (
    AuthenticatedTeacher,
    require_governed_user,
    require_platform_admin,
    require_teacher,
)
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/session", tags=["authentication"])
PlanningTimeChange = Literal[
    "much_less",
    "somewhat_less",
    "about_same",
    "somewhat_more",
    "much_more",
]
RolloutReadiness = Literal[
    "ready_now",
    "ready_minor_fixes",
    "needs_significant_fixes",
    "not_ready",
]


class SessionIdentityRead(BaseModel):
    id: str
    email: str
    display_name: str
    school_id: str
    roles: list[str]
    data_boundary: str


class PilotFeedbackStatusRead(BaseModel):
    survey_key: str = "pilot-rollout-2026-08"
    eligible: bool = False
    available: bool = False
    submitted: bool = False
    preferred_ready: bool = False
    fallback_ready: bool = False
    required_closeouts: int = 0
    completed_closeouts: int = 0
    required_next_week_plans: int = 0
    saved_next_week_plans: int = 0
    submitted_at: str | None = None


class PilotFeedbackWrite(BaseModel):
    overall_usefulness: int = Field(ge=1, le=5)
    planning_time_change: PlanningTimeChange
    most_useful: str = Field(min_length=1, max_length=1500)
    biggest_challenge: str = Field(min_length=1, max_length=1500)
    dislike_or_simplify: str = Field(default="", max_length=1500)
    recommended_improvement: str = Field(min_length=1, max_length=1500)
    rollout_readiness: RolloutReadiness


class PilotFeedbackSubmitRead(BaseModel):
    id: str
    submitted_at: str


class PilotFeedbackResultRead(BaseModel):
    id: str
    survey_key: str
    school_id: str
    school_name: str
    teacher_id: str
    teacher_name: str
    overall_usefulness: int
    planning_time_change: PlanningTimeChange
    most_useful: str
    biggest_challenge: str
    dislike_or_simplify: str
    recommended_improvement: str
    rollout_readiness: RolloutReadiness
    submitted_at: str


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Authenticated access token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Pilot feedback service returned invalid data")
    return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]


def _feedback_error(error: SupabaseRestError) -> HTTPException:
    if error.status_code in {400, 409, 422}:
        return HTTPException(status_code=422, detail="Pilot feedback could not be accepted")
    if error.status_code in {401, 403}:
        return HTTPException(status_code=403, detail="Pilot feedback is not authorized")
    return HTTPException(status_code=503, detail="Pilot feedback service is unavailable")


@router.get("", response_model=SessionIdentityRead)
def current_session(
    identity: Annotated[AuthenticatedTeacher, Depends(require_governed_user)],
) -> SessionIdentityRead:
    if identity.school_id is None:
        raise RuntimeError("Governed identity is missing a school")
    return SessionIdentityRead(
        id=identity.subject,
        email=identity.email,
        display_name=identity.display_name,
        school_id=identity.school_id,
        roles=sorted(identity.roles),
        data_boundary="teacher-and-curriculum-only",
    )


@router.get("/pilot-feedback/status", response_model=PilotFeedbackStatusRead)
def pilot_feedback_status(
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PilotFeedbackStatusRead:
    try:
        payload = _client(identity, settings).request("POST", "rpc/pilot_feedback_status", payload={})
    except SupabaseRestError as error:
        raise _feedback_error(error) from error
    rows = _records(payload)
    if not rows:
        return PilotFeedbackStatusRead()
    return PilotFeedbackStatusRead.model_validate(rows[0])


@router.post("/pilot-feedback", response_model=PilotFeedbackSubmitRead, status_code=201)
def submit_pilot_feedback(
    payload: PilotFeedbackWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PilotFeedbackSubmitRead:
    try:
        result = _client(identity, settings).request(
            "POST",
            "rpc/submit_pilot_feedback",
            payload={
                "target_overall_usefulness": payload.overall_usefulness,
                "target_planning_time_change": payload.planning_time_change,
                "target_most_useful": payload.most_useful.strip(),
                "target_biggest_challenge": payload.biggest_challenge.strip(),
                "target_dislike_or_simplify": payload.dislike_or_simplify.strip(),
                "target_recommended_improvement": payload.recommended_improvement.strip(),
                "target_rollout_readiness": payload.rollout_readiness,
            },
        )
    except SupabaseRestError as error:
        raise _feedback_error(error) from error
    rows = _records(result)
    if not rows:
        raise HTTPException(status_code=503, detail="Pilot feedback submission returned no record")
    return PilotFeedbackSubmitRead.model_validate(rows[0])


@router.get("/pilot-feedback/results", response_model=list[PilotFeedbackResultRead])
def pilot_feedback_results(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[PilotFeedbackResultRead]:
    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/platform_pilot_feedback_results",
            payload={},
        )
    except SupabaseRestError as error:
        raise _feedback_error(error) from error
    return [PilotFeedbackResultRead.model_validate(row) for row in _records(payload)]
