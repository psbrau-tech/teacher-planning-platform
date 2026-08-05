from __future__ import annotations

from collections import OrderedDict
from contextlib import suppress
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_teacher
from .curriculum_import import CurriculumLessonImport, validate_curriculum_import
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/curricula", tags=["curriculum"])


class CurriculumLessonWrite(BaseModel):
    sequence: int = Field(ge=1)
    unit_title: str = Field(min_length=1, max_length=160)
    lesson_title: str = Field(min_length=1, max_length=200)
    estimated_minutes: int = Field(gt=0)
    standards: list[str] = []
    learning_targets: list[str] = []
    assessment: str = ""
    can_split: bool = True


class CurriculumWrite(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=80)
    standards_family: str | None = Field(default=None, max_length=120)
    lessons: list[CurriculumLessonWrite] = Field(min_length=1)


class CurriculumRead(BaseModel):
    id: str
    school_id: str
    name: str
    version: str
    standards_family: str | None
    is_active: bool


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Pilot data service returned invalid data")
    return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]


def _text(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise HTTPException(status_code=503, detail=f"Pilot data response is missing {key}")
    return value


def _optional_text(record: dict[str, Any], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value else None


def _to_read(record: dict[str, Any]) -> CurriculumRead:
    active = record.get("is_active")
    if not isinstance(active, bool):
        raise HTTPException(status_code=503, detail="Pilot data response is missing is_active")
    return CurriculumRead(
        id=_text(record, "id"),
        school_id=_text(record, "school_id"),
        name=_text(record, "name"),
        version=_text(record, "version"),
        standards_family=_optional_text(record, "standards_family"),
        is_active=active,
    )


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _raise_data_error(error: SupabaseRestError, operation: str) -> None:
    if error.status_code in {401, 403}:
        raise HTTPException(status_code=403, detail="Pilot data access was denied") from error
    if error.status_code in {400, 409, 422}:
        raise HTTPException(status_code=409, detail=f"{operation} was rejected") from error
    raise HTTPException(status_code=503, detail="Pilot data service is unavailable") from error


@router.get("", response_model=list[CurriculumRead])
def list_curricula(
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[CurriculumRead]:
    if identity.school_id is None:
        raise HTTPException(status_code=403, detail="Pilot school assignment is required")
    try:
        rows = _records(
            _client(identity, settings).request(
                "GET",
                "curricula",
                params={
                    "school_id": f"eq.{identity.school_id}",
                    "is_active": "eq.true",
                    "select": "id,school_id,name,version,standards_family,is_active",
                    "order": "name.asc,version.desc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Curriculum load")
    return [_to_read(row) for row in rows]


@router.post("", response_model=CurriculumRead, status_code=201)
def create_curriculum(
    payload: CurriculumWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurriculumRead:
    if identity.school_id is None:
        raise HTTPException(status_code=403, detail="Pilot school assignment is required")
    if "teacher" not in identity.roles:
        raise HTTPException(status_code=403, detail="Teacher role is required")

    imported = validate_curriculum_import(
        [
            CurriculumLessonImport(
                sequence=lesson.sequence,
                unit_title=lesson.unit_title,
                lesson_title=lesson.lesson_title,
                estimated_minutes=lesson.estimated_minutes,
                standards=tuple(lesson.standards),
                learning_targets=tuple(lesson.learning_targets),
                assessment=lesson.assessment,
                can_split=lesson.can_split,
            )
            for lesson in payload.lessons
        ]
    )
    client = _client(identity, settings)
    curriculum_id: str | None = None
    try:
        curriculum_rows = _records(
            client.request(
                "POST",
                "curricula",
                payload={
                    "school_id": identity.school_id,
                    "name": payload.name.strip(),
                    "version": payload.version.strip(),
                    "standards_family": (
                        payload.standards_family.strip() if payload.standards_family else None
                    ),
                    "is_active": True,
                    "created_by": identity.subject,
                },
                prefer="return=representation",
            )
        )
        if not curriculum_rows:
            raise HTTPException(status_code=503, detail="Curriculum save returned no record")
        curriculum = curriculum_rows[0]
        curriculum_id = _text(curriculum, "id")

        unit_groups: OrderedDict[str, list[CurriculumLessonImport]] = OrderedDict()
        for lesson in imported:
            unit_groups.setdefault(lesson.unit_title, []).append(lesson)

        for unit_sequence, (unit_title, unit_lessons) in enumerate(unit_groups.items(), start=1):
            unit_rows = _records(
                client.request(
                    "POST",
                    "curriculum_units",
                    payload={
                        "curriculum_id": curriculum_id,
                        "sequence": unit_sequence,
                        "title": unit_title,
                    },
                    prefer="return=representation",
                )
            )
            if not unit_rows:
                raise HTTPException(
                    status_code=503,
                    detail="Curriculum unit save returned no record",
                )
            unit_id = _text(unit_rows[0], "id")
            client.request(
                "POST",
                "lessons",
                payload=[
                    {
                        "unit_id": unit_id,
                        "sequence": lesson.sequence,
                        "title": lesson.lesson_title,
                        "estimated_minutes": lesson.estimated_minutes,
                        "can_split": lesson.can_split,
                        "standards": list(lesson.standards),
                        "learning_targets": list(lesson.learning_targets),
                        "assessments": [lesson.assessment] if lesson.assessment else [],
                    }
                    for lesson in unit_lessons
                ],
                prefer="return=minimal",
            )
        return _to_read(curriculum)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SupabaseRestError as error:
        if curriculum_id is not None:
            with suppress(SupabaseRestError):
                client.request(
                    "DELETE",
                    "curricula",
                    params={"id": f"eq.{curriculum_id}"},
                )
        _raise_data_error(error, "Curriculum save")
