from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_platform_admin, require_teacher
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/baseline", tags=["baseline"])

PlanningTimeBefore = Literal[
    "under_30",
    "30_60",
    "61_90",
    "91_120",
    "121_180",
    "over_180",
    "not_sure",
]
FrequencyBefore = Literal["never", "rarely", "sometimes", "often", "very_often"]


class BaselineStatusRead(BaseModel):
    survey_key: str = "teacher-baseline-2026-08"
    eligible: bool = False
    available: bool = False
    submitted: bool = False
    submitted_at: str | None = None


class BaselineWrite(BaseModel):
    planning_time_before: PlanningTimeBefore
    plan_usefulness_before: int = Field(ge=1, le=5)
    submission_burden_before: int = Field(ge=1, le=5)
    reflection_review_frequency_before: FrequencyBefore
    plc_use_frequency_before: FrequencyBefore
    biggest_burden_before: str = Field(default="", max_length=1000)


class BaselineSubmitRead(BaseModel):
    id: str
    submitted_at: str


class BaselineResultRead(BaseModel):
    id: str
    survey_key: str
    school_id: str
    school_name: str
    planning_time_before: str
    plan_usefulness_before: int
    submission_burden_before: int
    reflection_review_frequency_before: FrequencyBefore
    plc_use_frequency_before: FrequencyBefore
    biggest_burden_before: str
    submitted_at: str


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Authenticated access token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(
            status_code=503,
            detail="Teacher baseline service returned invalid data",
        )
    return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]


def _baseline_error(error: SupabaseRestError) -> HTTPException:
    if error.status_code in {400, 409, 422}:
        return HTTPException(status_code=422, detail="Teacher baseline could not be accepted")
    if error.status_code in {401, 403}:
        return HTTPException(status_code=403, detail="Teacher baseline is not authorized")
    return HTTPException(status_code=503, detail="Teacher baseline service is unavailable")


@router.get("/status", response_model=BaselineStatusRead)
def baseline_status(
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BaselineStatusRead:
    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/teacher_baseline_status",
            payload={},
        )
    except SupabaseRestError as error:
        raise _baseline_error(error) from error
    rows = _records(payload)
    if not rows:
        return BaselineStatusRead()
    return BaselineStatusRead.model_validate(rows[0])


@router.post("", response_model=BaselineSubmitRead, status_code=201)
def submit_baseline(
    payload: BaselineWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BaselineSubmitRead:
    try:
        result = _client(identity, settings).request(
            "POST",
            "rpc/submit_teacher_baseline",
            payload={
                "target_planning_time_before": payload.planning_time_before,
                "target_plan_usefulness_before": payload.plan_usefulness_before,
                "target_submission_burden_before": payload.submission_burden_before,
                "target_reflection_review_frequency_before": (
                    payload.reflection_review_frequency_before
                ),
                "target_plc_use_frequency_before": payload.plc_use_frequency_before,
                "target_biggest_burden_before": payload.biggest_burden_before.strip(),
            },
        )
    except SupabaseRestError as error:
        raise _baseline_error(error) from error
    rows = _records(result)
    if not rows:
        raise HTTPException(
            status_code=503,
            detail="Teacher baseline submission returned no record",
        )
    return BaselineSubmitRead.model_validate(rows[0])


@router.get("/results", response_model=list[BaselineResultRead])
def baseline_results(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[BaselineResultRead]:
    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/platform_teacher_baseline_results",
            payload={},
        )
    except SupabaseRestError as error:
        raise _baseline_error(error) from error
    return [BaselineResultRead.model_validate(row) for row in _records(payload)]
