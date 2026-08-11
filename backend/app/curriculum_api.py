from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from io import BytesIO
import re
from typing import Annotated, Any, NoReturn, cast
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Response
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
    estimated_minutes: int | None = Field(default=None, gt=0)
    standards: list[str] = Field(default_factory=list)
    learning_targets: list[str] = Field(default_factory=list)
    assessment: str = ""
    can_split: bool = True


class CurriculumWrite(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=80)
    standards_family: str | None = Field(default=None, max_length=120)
    lessons: list[CurriculumLessonWrite] = Field(default_factory=list)


class CurriculumRevisionWrite(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=80)
    lessons: list[CurriculumLessonWrite] = Field(min_length=1)


class CurriculumCopyWrite(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=80)


class CurriculumRead(BaseModel):
    id: str
    school_id: str
    name: str
    version: str
    standards_family: str | None
    is_active: bool


class CurriculumLessonRead(BaseModel):
    sequence: int
    unit_title: str
    lesson_title: str
    estimated_minutes: int | None
    standards: list[str]
    learning_targets: list[str]
    assessment: str
    can_split: bool


class CurriculumDetailRead(CurriculumRead):
    lessons: list[CurriculumLessonRead]
    active_class_count: int
    locked_through_sequence: int


class CurriculumRevisionRead(BaseModel):
    curriculum: CurriculumDetailRead
    replaced_curriculum_id: str
    active_classes_updated: int


@dataclass(frozen=True, slots=True)
class _StoredLesson:
    sequence: int
    unit_title: str
    lesson_title: str
    estimated_minutes: int | None
    standards: tuple[str, ...]
    learning_targets: tuple[str, ...]
    assessment: str
    can_split: bool


JsonRecord = dict[str, Any]


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Pilot data service returned invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise HTTPException(status_code=503, detail=f"Pilot data response is missing {key}")
    return value


def _optional_text(record: JsonRecord, key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value else None


def _optional_positive_int(record: JsonRecord, key: str) -> int | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise HTTPException(status_code=503, detail=f"Pilot data response has invalid {key}")
    return value


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


def _to_read(record: JsonRecord) -> CurriculumRead:
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


def _raise_data_error(error: SupabaseRestError, operation: str) -> NoReturn:
    if error.status_code in {401, 403}:
        raise HTTPException(status_code=403, detail="Pilot data access was denied") from error
    if error.status_code in {400, 409, 422}:
        raise HTTPException(status_code=409, detail=f"{operation} was rejected") from error
    raise HTTPException(status_code=503, detail="Pilot data service is unavailable") from error


def _require_teacher(identity: AuthenticatedTeacher) -> str:
    if identity.school_id is None:
        raise HTTPException(status_code=403, detail="Pilot school assignment is required")
    if "teacher" not in identity.roles:
        raise HTTPException(status_code=403, detail="Teacher role is required")
    return identity.school_id


def _owned_curriculum(
    client: SupabaseRestClient,
    identity: AuthenticatedTeacher,
    curriculum_id: str,
) -> JsonRecord:
    try:
        rows = _records(
            client.request(
                "GET",
                "curricula",
                params={
                    "id": f"eq.{curriculum_id}",
                    "created_by": f"eq.{identity.subject}",
                    "is_active": "eq.true",
                    "select": (
                        "id,school_id,name,version,standards_family,is_active,created_by"
                    ),
                    "limit": "1",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Curriculum load")
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Curriculum was not found in your active curricula",
        )
    return rows[0]


def _stored_lessons(client: SupabaseRestClient, curriculum_id: str) -> list[_StoredLesson]:
    try:
        units = _records(
            client.request(
                "GET",
                "curriculum_units",
                params={
                    "curriculum_id": f"eq.{curriculum_id}",
                    "select": "id,sequence,title",
                    "order": "sequence.asc",
                },
            )
        )
        result: list[_StoredLesson] = []
        global_sequence = 1
        for unit in units:
            lesson_rows = _records(
                client.request(
                    "GET",
                    "lessons",
                    params={
                        "unit_id": f"eq.{_text(unit, 'id')}",
                        "select": (
                            "id,sequence,title,estimated_minutes,standards,learning_targets,"
                            "assessments,can_split"
                        ),
                        "order": "sequence.asc",
                    },
                )
            )
            for lesson in lesson_rows:
                can_split = lesson.get("can_split")
                if not isinstance(can_split, bool):
                    raise HTTPException(
                        status_code=503,
                        detail="Pilot data response has invalid can_split",
                    )
                result.append(
                    _StoredLesson(
                        sequence=global_sequence,
                        unit_title=_text(unit, "title"),
                        lesson_title=_text(lesson, "title"),
                        estimated_minutes=_optional_positive_int(
                            lesson,
                            "estimated_minutes",
                        ),
                        standards=_strings(lesson.get("standards")),
                        learning_targets=_strings(lesson.get("learning_targets")),
                        assessment="; ".join(_strings(lesson.get("assessments"))),
                        can_split=can_split,
                    )
                )
                global_sequence += 1
        return result
    except SupabaseRestError as error:
        _raise_data_error(error, "Curriculum lesson load")


def _to_lesson_read(lesson: _StoredLesson) -> CurriculumLessonRead:
    return CurriculumLessonRead(
        sequence=lesson.sequence,
        unit_title=lesson.unit_title,
        lesson_title=lesson.lesson_title,
        estimated_minutes=lesson.estimated_minutes,
        standards=list(lesson.standards),
        learning_targets=list(lesson.learning_targets),
        assessment=lesson.assessment,
        can_split=lesson.can_split,
    )


def _to_import(lesson: _StoredLesson) -> CurriculumLessonImport:
    return CurriculumLessonImport(
        sequence=lesson.sequence,
        unit_title=lesson.unit_title,
        lesson_title=lesson.lesson_title,
        estimated_minutes=lesson.estimated_minutes,
        standards=lesson.standards,
        learning_targets=lesson.learning_targets,
        assessment=lesson.assessment,
        can_split=lesson.can_split,
    )


def _normalize_lessons(
    lessons: list[CurriculumLessonWrite],
) -> tuple[CurriculumLessonImport, ...]:
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
            for lesson in lessons
        ]
    )
    expected = list(range(1, len(imported) + 1))
    if [lesson.sequence for lesson in imported] != expected:
        raise ValueError("lesson sequence must be contiguous starting at 1")
    return imported


def _active_assignment_ids(
    client: SupabaseRestClient,
    identity: AuthenticatedTeacher,
    curriculum_id: str,
) -> list[str]:
    try:
        rows = _records(
            client.request(
                "GET",
                "teaching_assignments",
                params={
                    "teacher_id": f"eq.{identity.subject}",
                    "curriculum_id": f"eq.{curriculum_id}",
                    "is_active": "eq.true",
                    "select": "id",
                    "order": "starts_on.asc,course_name.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Curriculum class load")
    return [_text(row, "id") for row in rows]


def _sequence_position(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise HTTPException(status_code=503, detail="Pilot pacing history is invalid")
    try:
        sequence = int(float(value))
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Pilot pacing history is invalid") from error
    if sequence < 1:
        raise HTTPException(status_code=503, detail="Pilot pacing history is invalid")
    return sequence


def _locked_through_sequence(client: SupabaseRestClient, assignment_ids: list[str]) -> int:
    locked = 0
    try:
        for assignment_id in assignment_ids:
            rows = _records(
                client.request(
                    "GET",
                    "scheduled_lessons",
                    params={
                        "teaching_assignment_id": f"eq.{assignment_id}",
                        "select": "sequence_position",
                    },
                )
            )
            for row in rows:
                locked = max(locked, _sequence_position(row.get("sequence_position")))
    except SupabaseRestError as error:
        _raise_data_error(error, "Curriculum pacing history load")
    return locked


def _same_locked_content(old: _StoredLesson, new: CurriculumLessonImport) -> bool:
    return (
        old.unit_title.strip() == new.unit_title.strip()
        and old.lesson_title.strip() == new.lesson_title.strip()
        and old.estimated_minutes == new.estimated_minutes
        and old.learning_targets == new.learning_targets
        and old.assessment.strip() == new.assessment.strip()
        and old.can_split == new.can_split
    )


def _contiguous_unit_groups(
    lessons: tuple[CurriculumLessonImport, ...],
) -> list[tuple[str, list[CurriculumLessonImport]]]:
    """Preserve teacher-authored pacing order even when a unit title repeats later."""
    groups: list[tuple[str, list[CurriculumLessonImport]]] = []
    for lesson in lessons:
        unit_title = lesson.unit_title.strip()
        if groups and groups[-1][0] == unit_title:
            groups[-1][1].append(lesson)
        else:
            groups.append((unit_title, [lesson]))
    return groups


def _save_curriculum(
    *,
    client: SupabaseRestClient,
    identity: AuthenticatedTeacher,
    school_id: str,
    name: str,
    version: str,
    standards_family: str | None,
    lessons: tuple[CurriculumLessonImport, ...],
) -> CurriculumRead:
    curriculum_id: str | None = None
    try:
        curriculum_rows = _records(
            client.request(
                "POST",
                "curricula",
                payload={
                    "school_id": school_id,
                    "name": name.strip(),
                    "version": version.strip(),
                    "standards_family": standards_family,
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

        for unit_sequence, (unit_title, unit_lessons) in enumerate(
            _contiguous_unit_groups(lessons),
            start=1,
        ):
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
                        "title": lesson.lesson_title.strip(),
                        "estimated_minutes": lesson.estimated_minutes,
                        "can_split": lesson.can_split,
                        "standards": list(lesson.standards),
                        "learning_targets": list(lesson.learning_targets),
                        "assessments": [lesson.assessment.strip()] if lesson.assessment.strip() else [],
                    }
                    for lesson in unit_lessons
                ],
                prefer="return=minimal",
            )
        return _to_read(curriculum)
    except SupabaseRestError as error:
        if curriculum_id is not None:
            with suppress(SupabaseRestError):
                client.request(
                    "DELETE",
                    "curricula",
                    params={"id": f"eq.{curriculum_id}"},
                )
        _raise_data_error(error, "Curriculum save")


def _detail(
    *,
    client: SupabaseRestClient,
    identity: AuthenticatedTeacher,
    curriculum: JsonRecord,
) -> CurriculumDetailRead:
    curriculum_id = _text(curriculum, "id")
    assignment_ids = _active_assignment_ids(client, identity, curriculum_id)
    return CurriculumDetailRead(
        **_to_read(curriculum).model_dump(),
        lessons=[_to_lesson_read(lesson) for lesson in _stored_lessons(client, curriculum_id)],
        active_class_count=len(assignment_ids),
        locked_through_sequence=_locked_through_sequence(client, assignment_ids),
    )


def _column_name(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _xlsx_bytes(detail: CurriculumDetailRead) -> bytes:
    headers = [
        "Unit / Topic",
        "Lesson / Focus",
        "Learning Target(s)",
        "Assessment / Evidence",
        "Optional Minutes Override",
    ]
    data_rows = [
        [
            lesson.unit_title,
            lesson.lesson_title,
            "; ".join(lesson.learning_targets),
            lesson.assessment,
            "" if lesson.estimated_minutes is None else str(lesson.estimated_minutes),
        ]
        for lesson in detail.lessons
    ]

    xml_rows: list[str] = []
    for row_number, values in enumerate([headers, *data_rows], start=1):
        cells = []
        for column, value in enumerate(values):
            reference = f"{_column_name(column)}{row_number}"
            cells.append(
                f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">'
                f"{escape(value)}</t></is></c>"
            )
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        '</worksheet>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Curriculum &amp; Pacing" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as workbook_zip:
        workbook_zip.writestr("[Content_Types].xml", content_types)
        workbook_zip.writestr("_rels/.rels", root_rels)
        workbook_zip.writestr("xl/workbook.xml", workbook)
        workbook_zip.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        workbook_zip.writestr("xl/worksheets/sheet1.xml", worksheet)
    return buffer.getvalue()


@router.get("", response_model=list[CurriculumRead])
def list_curricula(
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[CurriculumRead]:
    """Return only active curricula created by the teacher using Course Setup."""
    school_id = _require_teacher(identity)
    try:
        rows = _records(
            _client(identity, settings).request(
                "GET",
                "curricula",
                params={
                    "school_id": f"eq.{school_id}",
                    "created_by": f"eq.{identity.subject}",
                    "is_active": "eq.true",
                    "select": "id,school_id,name,version,standards_family,is_active",
                    "order": "name.asc,version.desc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Curriculum load")
    return [_to_read(row) for row in rows]


@router.get("/{curriculum_id}", response_model=CurriculumDetailRead)
def get_curriculum(
    curriculum_id: str,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurriculumDetailRead:
    _require_teacher(identity)
    client = _client(identity, settings)
    curriculum = _owned_curriculum(client, identity, curriculum_id)
    return _detail(client=client, identity=identity, curriculum=curriculum)


@router.get("/{curriculum_id}/export.xlsx")
def export_curriculum(
    curriculum_id: str,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    _require_teacher(identity)
    client = _client(identity, settings)
    curriculum = _owned_curriculum(client, identity, curriculum_id)
    detail = _detail(client=client, identity=identity, curriculum=curriculum)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{detail.name}-{detail.version}").strip("-")
    return Response(
        content=_xlsx_bytes(detail),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe_name or "curriculum"}.xlsx"'},
    )


@router.post("", response_model=CurriculumRead, status_code=201)
def create_curriculum(
    payload: CurriculumWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurriculumRead:
    school_id = _require_teacher(identity)
    try:
        imported = _normalize_lessons(payload.lessons) if payload.lessons else ()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _save_curriculum(
        client=_client(identity, settings),
        identity=identity,
        school_id=school_id,
        name=payload.name,
        version=payload.version,
        standards_family=(
            payload.standards_family.strip() if payload.standards_family else None
        ),
        lessons=imported,
    )


@router.post("/{curriculum_id}/copy", response_model=CurriculumRead, status_code=201)
def copy_curriculum(
    curriculum_id: str,
    payload: CurriculumCopyWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurriculumRead:
    school_id = _require_teacher(identity)
    client = _client(identity, settings)
    source = _owned_curriculum(client, identity, curriculum_id)
    lessons = tuple(_to_import(lesson) for lesson in _stored_lessons(client, curriculum_id))
    return _save_curriculum(
        client=client,
        identity=identity,
        school_id=school_id,
        name=payload.name,
        version=payload.version,
        standards_family=_optional_text(source, "standards_family"),
        lessons=lessons,
    )


@router.put("/{curriculum_id}/pacing", response_model=CurriculumRevisionRead)
def revise_curriculum(
    curriculum_id: str,
    payload: CurriculumRevisionWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurriculumRevisionRead:
    school_id = _require_teacher(identity)
    client = _client(identity, settings)
    source = _owned_curriculum(client, identity, curriculum_id)
    current = _stored_lessons(client, curriculum_id)
    assignment_ids = _active_assignment_ids(client, identity, curriculum_id)
    locked = _locked_through_sequence(client, assignment_ids)
    try:
        imported = _normalize_lessons(payload.lessons)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if len(imported) < locked:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Lessons 1 through {locked} are already scheduled in a class using this "
                "curriculum and must remain in the current-year history. Create a separate "
                "copy for a class if it needs a different path."
            ),
        )
    if locked > len(current):
        raise HTTPException(status_code=503, detail="Curriculum pacing history is inconsistent")
    for index in range(locked):
        if not _same_locked_content(current[index], imported[index]):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Lesson {index + 1} is already scheduled in a class using this curriculum. "
                    "Only the unscheduled portion of a shared current-year curriculum can be "
                    "changed. Create a separate copy for a class when its future path differs."
                ),
            )

    revised_lessons = tuple(_to_import(item) for item in current[:locked]) + imported[locked:]
    revised = _save_curriculum(
        client=client,
        identity=identity,
        school_id=school_id,
        name=payload.name,
        version=payload.version,
        standards_family=_optional_text(source, "standards_family"),
        lessons=revised_lessons,
    )
    try:
        result = client.request(
            "POST",
            "rpc/replace_teacher_curriculum_version",
            payload={
                "prior_curriculum_id": curriculum_id,
                "revised_curriculum_id": revised.id,
            },
        )
    except SupabaseRestError as error:
        with suppress(SupabaseRestError):
            client.request("DELETE", "curricula", params={"id": f"eq.{revised.id}"})
        _raise_data_error(error, "Curriculum revision activation")

    updated_count = result if isinstance(result, int) and not isinstance(result, bool) else len(assignment_ids)
    revised_record = _owned_curriculum(client, identity, revised.id)
    return CurriculumRevisionRead(
        curriculum=_detail(client=client, identity=identity, curriculum=revised_record),
        replaced_curriculum_id=curriculum_id,
        active_classes_updated=updated_count,
    )


@router.delete("/{curriculum_id}", status_code=204)
def archive_curriculum(
    curriculum_id: str,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    _require_teacher(identity)
    client = _client(identity, settings)
    _owned_curriculum(client, identity, curriculum_id)
    active_assignments = _active_assignment_ids(client, identity, curriculum_id)
    if active_assignments:
        raise HTTPException(
            status_code=409,
            detail=(
                "This curriculum is still attached to an active class. "
                "Replace or remove it from that class first."
            ),
        )
    try:
        rows = _records(
            client.request(
                "PATCH",
                "curricula",
                params={
                    "id": f"eq.{curriculum_id}",
                    "created_by": f"eq.{identity.subject}",
                    "is_active": "eq.true",
                },
                payload={"is_active": False},
                prefer="return=representation",
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Curriculum retirement")
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Curriculum was not found in your active curricula",
        )
    return Response(status_code=204)
