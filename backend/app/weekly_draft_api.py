from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings
from .supabase_persistence import PersistenceError, SupabaseWeeklyDraftStore
from .supabase_rest import SupabaseRestClient, SupabaseRestError
from .weekly_drafts import WeeklyDraft, WeeklyDraftStore, weekly_draft_store

router = APIRouter(prefix="/api/v1/weekly-drafts", tags=["planning"])


class WeeklyDraftWrite(BaseModel):
    assignment_id: str = Field(min_length=1)
    week_start: date
    content: dict[str, str]
    expected_revision: int | None = Field(default=None, ge=0)


class WeeklySubmitWrite(BaseModel):
    assignment_id: str = Field(min_length=1)
    week_start: date
    expected_revision: int = Field(ge=1)


class WeeklyDraftRead(BaseModel):
    id: str
    teacher_id: str
    assignment_id: str
    week_start: date
    content: dict[str, str]
    revision: int
    updated_at: str
    is_draft: bool
    submission_status: str
    submitted_at: str | None = None


def _status(is_draft: bool, submitted_at: str | None) -> str:
    if not is_draft and submitted_at is not None:
        return "submitted"
    if submitted_at is not None:
        return "revised_after_submission"
    return "not_submitted"


def _store_for(
    teacher: AuthenticatedTeacher,
    settings: Settings,
) -> WeeklyDraftStore | SupabaseWeeklyDraftStore:
    if teacher.access_token is None:
        return weekly_draft_store
    return SupabaseWeeklyDraftStore(
        client=SupabaseRestClient.from_settings(
            settings,
            access_token=teacher.access_token,
        ),
        authenticated_teacher_id=teacher.subject,
    )


def _submission_state(
    draft: WeeklyDraft,
    teacher: AuthenticatedTeacher,
    settings: Settings,
) -> tuple[bool, str | None]:
    if teacher.access_token is None:
        return draft.is_draft, draft.submitted_at.isoformat() if draft.submitted_at else None
    try:
        payload = SupabaseRestClient.from_settings(
            settings,
            access_token=teacher.access_token,
        ).request(
            "GET",
            "weekly_plan_snapshots",
            params={
                "id": f"eq.{draft.id}",
                "select": "is_draft,approved_at",
                "limit": "1",
            },
        )
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise HTTPException(status_code=403, detail="Pilot data access was denied") from error
        raise HTTPException(
            status_code=503,
            detail="Weekly submission state is unavailable",
        ) from error
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise HTTPException(status_code=503, detail="Weekly submission state is unavailable")
    row = payload[0]
    is_draft = row.get("is_draft")
    approved_at = row.get("approved_at")
    if not isinstance(is_draft, bool):
        raise HTTPException(status_code=503, detail="Weekly submission state is invalid")
    submitted_at = approved_at if isinstance(approved_at, str) and approved_at else None
    return is_draft, submitted_at


def _to_read_model(
    draft: WeeklyDraft,
    teacher: AuthenticatedTeacher,
    settings: Settings,
) -> WeeklyDraftRead:
    is_draft, submitted_at = _submission_state(draft, teacher, settings)
    return WeeklyDraftRead(
        id=draft.id,
        teacher_id=draft.teacher_id,
        assignment_id=draft.assignment_id,
        week_start=draft.week_start,
        content=draft.content,
        revision=draft.revision,
        updated_at=draft.updated_at.isoformat(),
        is_draft=is_draft,
        submission_status=_status(is_draft, submitted_at),
        submitted_at=submitted_at,
    )


@router.get("", response_model=WeeklyDraftRead)
def get_weekly_draft(
    assignment_id: Annotated[str, Query(min_length=1)],
    week_start: date,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklyDraftRead:
    try:
        draft = _store_for(teacher, settings).get(
            teacher.subject,
            assignment_id,
            week_start,
        )
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if draft is None:
        raise HTTPException(status_code=404, detail="Weekly draft not found")
    return _to_read_model(draft, teacher, settings)


@router.put("", response_model=WeeklyDraftRead)
def save_weekly_draft(
    payload: WeeklyDraftWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklyDraftRead:
    try:
        draft = _store_for(teacher, settings).save(
            teacher_id=teacher.subject,
            assignment_id=payload.assignment_id,
            week_start=payload.week_start,
            content=payload.content,
            expected_revision=payload.expected_revision,
        )
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _to_read_model(draft, teacher, settings)


@router.post("/submit", response_model=WeeklyDraftRead)
def submit_weekly_draft(
    payload: WeeklySubmitWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklyDraftRead:
    store = _store_for(teacher, settings)
    if teacher.access_token is None:
        try:
            draft = weekly_draft_store.submit(
                teacher_id=teacher.subject,
                assignment_id=payload.assignment_id,
                week_start=payload.week_start,
                expected_revision=payload.expected_revision,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _to_read_model(draft, teacher, settings)

    try:
        current = store.get(teacher.subject, payload.assignment_id, payload.week_start)
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if current is None:
        raise HTTPException(status_code=404, detail="Weekly draft not found")

    try:
        SupabaseRestClient.from_settings(
            settings,
            access_token=teacher.access_token,
        ).request(
            "POST",
            "rpc/submit_weekly_plan",
            payload={
                "target_snapshot_id": current.id,
                "expected_revision": payload.expected_revision,
            },
        )
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise HTTPException(
                status_code=403,
                detail="Weekly plan submission is not authorized",
            ) from error
        if error.status_code in {400, 409}:
            raise HTTPException(status_code=409, detail="Weekly plan revision conflict") from error
        raise HTTPException(
            status_code=503,
            detail="Weekly plan submission is unavailable",
        ) from error

    refreshed = store.get(teacher.subject, payload.assignment_id, payload.week_start)
    if refreshed is None:
        raise HTTPException(status_code=503, detail="Submitted weekly plan could not be reopened")
    return _to_read_model(refreshed, teacher, settings)
