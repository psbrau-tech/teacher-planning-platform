from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings
from .supabase_persistence import (
    PersistenceError,
    SupabaseFridayValidationStore,
    SupabaseWeeklyDraftStore,
)
from .supabase_rest import SupabaseRestClient, SupabaseRestError
from .week_dates import require_monday
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


def _reflection_complete(content: dict[str, str]) -> bool:
    raw = content.get("reflection", "")
    if not raw:
        return False
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    return all(
        isinstance(parsed.get(f"reflect_{index}"), str)
        and bool(parsed[f"reflect_{index}"].strip())
        for index in range(1, 13)
    )


def _store_for(
    teacher: AuthenticatedTeacher,
    settings: Settings,
) -> WeeklyDraftStore | SupabaseWeeklyDraftStore:
    if teacher.access_token is None:
        return weekly_draft_store
    return SupabaseWeeklyDraftStore(
        client=SupabaseRestClient.from_settings(settings, access_token=teacher.access_token),
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
            settings, access_token=teacher.access_token
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
        raise HTTPException(status_code=503, detail="Weekly submission state is unavailable") from error
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


def _submission_kind(
    current: WeeklyDraft,
    teacher: AuthenticatedTeacher,
    settings: Settings,
) -> str:
    """Classify the explicit submit action from governed workflow state.

    A lesson-plan submission occurs before Friday closeout. A completed packet requires both
    a saved Friday validation and all 12 teacher-authored reflection prompts. This avoids
    guessing from date/time while preserving the already separate teacher UI actions.
    """
    if teacher.access_token is None or not _reflection_complete(current.content):
        return "lesson_plan"
    try:
        validation = SupabaseFridayValidationStore(
            client=SupabaseRestClient.from_settings(
                settings, access_token=teacher.access_token
            ),
            authenticated_teacher_id=teacher.subject,
        ).get(
            teacher.subject,
            UUID(current.assignment_id),
            current.week_start,
        )
    except (PersistenceError, ValueError) as error:
        if isinstance(error, PersistenceError):
            raise HTTPException(status_code=error.status_code, detail=str(error)) from error
        raise HTTPException(status_code=409, detail="Friday closeout context is invalid") from error
    return "completed_packet" if validation is not None else "lesson_plan"


@router.get("", response_model=WeeklyDraftRead)
def get_weekly_draft(
    assignment_id: Annotated[str, Query(min_length=1)],
    week_start: date,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklyDraftRead:
    require_monday(week_start)
    try:
        draft = _store_for(teacher, settings).get(teacher.subject, assignment_id, week_start)
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
    require_monday(payload.week_start)
    store = _store_for(teacher, settings)
    try:
        current = store.get(teacher.subject, payload.assignment_id, payload.week_start)
        if (
            current is not None
            and payload.expected_revision == current.revision
            and current.content == payload.content
        ):
            return _to_read_model(current, teacher, settings)
        draft = store.save(
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


@router.put("/closeout", response_model=WeeklyDraftRead)
def save_friday_closeout(
    payload: WeeklyDraftWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklyDraftRead:
    """Save Friday reflection/closeout without requiring unrelated planning fields."""
    require_monday(payload.week_start)
    if teacher.access_token is None:
        try:
            draft = weekly_draft_store.save(
                teacher_id=teacher.subject,
                assignment_id=payload.assignment_id,
                week_start=payload.week_start,
                content=payload.content,
                expected_revision=payload.expected_revision,
                require_planning_fields=False,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _to_read_model(draft, teacher, settings)

    store = _store_for(teacher, settings)
    try:
        current = store.get(teacher.subject, payload.assignment_id, payload.week_start)
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if current is not None and payload.expected_revision != current.revision:
        raise HTTPException(status_code=409, detail="weekly draft revision conflict")
    if current is None and payload.expected_revision not in (None, 0):
        raise HTTPException(status_code=409, detail="weekly draft does not exist")
    if current is not None and current.content == payload.content:
        return _to_read_model(current, teacher, settings)

    client = SupabaseRestClient.from_settings(settings, access_token=teacher.access_token)
    try:
        if current is None:
            rows = client.request(
                "POST",
                "weekly_plan_snapshots",
                payload={
                    "teaching_assignment_id": payload.assignment_id,
                    "week_start": payload.week_start.isoformat(),
                    "week_end": (payload.week_start + timedelta(days=6)).isoformat(),
                    "source_data": dict(payload.content),
                    "updated_by": teacher.subject,
                    "is_draft": True,
                },
                prefer="return=representation",
            )
        else:
            rows = client.request(
                "PATCH",
                "weekly_plan_snapshots",
                params={"id": f"eq.{current.id}", "revision": f"eq.{current.revision}"},
                payload={
                    "source_data": dict(payload.content),
                    "updated_by": teacher.subject,
                    "is_draft": True,
                },
                prefer="return=representation",
            )
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise HTTPException(status_code=403, detail="Friday closeout save is not authorized") from error
        if error.status_code in {400, 409, 422}:
            raise HTTPException(status_code=409, detail="Friday closeout revision conflict") from error
        raise HTTPException(status_code=503, detail="Friday closeout save is unavailable") from error
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=409, detail="Friday closeout revision conflict")
    refreshed = store.get(teacher.subject, payload.assignment_id, payload.week_start)
    if refreshed is None:
        raise HTTPException(status_code=503, detail="Friday closeout could not be reopened")
    return _to_read_model(refreshed, teacher, settings)


@router.post("/submit", response_model=WeeklyDraftRead)
def submit_weekly_draft(
    payload: WeeklySubmitWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklyDraftRead:
    require_monday(payload.week_start)
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

    submission_kind = _submission_kind(current, teacher, settings)
    try:
        SupabaseRestClient.from_settings(settings, access_token=teacher.access_token).request(
            "POST",
            "rpc/submit_weekly_plan_typed",
            payload={
                "target_snapshot_id": current.id,
                "expected_revision": payload.expected_revision,
                "target_submission_kind": submission_kind,
            },
        )
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise HTTPException(status_code=403, detail="Weekly plan submission is not authorized") from error
        if error.status_code in {400, 409, 422}:
            raise HTTPException(status_code=409, detail="Weekly plan revision conflict") from error
        raise HTTPException(status_code=503, detail="Weekly plan submission is unavailable") from error
    refreshed = store.get(teacher.subject, payload.assignment_id, payload.week_start)
    if refreshed is None:
        raise HTTPException(status_code=503, detail="Submitted weekly plan could not be reopened")
    return _to_read_model(refreshed, teacher, settings)
