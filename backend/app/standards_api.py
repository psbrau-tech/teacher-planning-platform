from __future__ import annotations

from datetime import date
from typing import Annotated, Any, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_platform_admin, require_teacher
from .settings import Settings, get_settings
from .standards_catalog_api import CatalogCategoryRead, CatalogCourseRead
from .supabase_persistence import PersistenceError, SupabaseTeachingAssignmentStore
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/standards", tags=["standards"])
JsonRecord = dict[str, Any]


class StandardSourceRead(BaseModel):
    id: UUID
    source_key: str
    authority: str
    title: str
    edition: str
    landing_url: str
    snapshot_id: UUID
    source_version: str | None
    retrieved_at: str
    resolved_document_url: str
    relationship: str = "primary"


class StandardCourseRead(BaseModel):
    id: UUID
    source_id: UUID
    course_key: str
    display_name: str
    source_course_code: str | None
    grade_band: str | None
    is_pilot_allowed: bool = True


class StandardEntryRead(BaseModel):
    id: UUID
    code: str
    text: str
    parent_code: str | None
    strand: str | None
    sequence: int
    source_id: UUID | None = None
    snapshot_id: UUID | None = None
    authority: str | None = None
    source_title: str | None = None
    relationship: str | None = None


class AssignmentStandardsRead(BaseModel):
    assignment_id: UUID
    week_start: date
    mapped: bool
    source: StandardSourceRead | None = None
    sources: list[StandardSourceRead] = Field(default_factory=list)
    course: StandardCourseRead | None = None
    catalog_category: CatalogCategoryRead | None = None
    catalog_course: CatalogCourseRead | None = None
    standards: list[StandardEntryRead] = Field(default_factory=list)
    selected_entry_ids: list[UUID] = Field(default_factory=list)


class WeeklyStandardsWrite(BaseModel):
    standard_entry_ids: list[UUID] = Field(default_factory=list, max_length=20)


class WeeklyStandardsWriteResult(BaseModel):
    selected_count: int


class AdminSourceRead(BaseModel):
    id: UUID
    source_key: str
    authority: str
    title: str
    edition: str
    approved_snapshot_id: UUID | None
    is_active: bool
    discovery_status: str
    catalog_category_name: str | None


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Pilot data service returned invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _required_text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=503, detail="Pilot standards data is invalid")
    return value.strip()


def _optional_text(record: JsonRecord, key: str) -> str | None:
    value = record.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _required_uuid(record: JsonRecord, key: str) -> UUID:
    try:
        return UUID(_required_text(record, key))
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Pilot standards data is invalid") from error


def _optional_uuid(record: JsonRecord, key: str) -> UUID | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Pilot standards data is invalid") from error


def _required_bool(record: JsonRecord, key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise HTTPException(status_code=503, detail="Pilot standards data is invalid")
    return value


def _required_int(record: JsonRecord, key: str) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=503, detail="Pilot standards data is invalid")
    return value


def _raise_data_error(error: SupabaseRestError, operation: str) -> NoReturn:
    if error.status_code in {401, 403}:
        raise HTTPException(status_code=403, detail="Pilot standards access was denied") from error
    if error.status_code in {400, 409, 422}:
        raise HTTPException(status_code=409, detail=f"{operation} was rejected") from error
    raise HTTPException(status_code=503, detail="Pilot standards service is unavailable") from error


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _require_assignment(
    client: SupabaseRestClient,
    identity: AuthenticatedTeacher,
    assignment_id: UUID,
) -> None:
    store = SupabaseTeachingAssignmentStore(client, identity.subject)
    try:
        assignment = store.get(identity.subject, str(assignment_id))
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if assignment is None:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")


def _course_read(record: JsonRecord) -> StandardCourseRead:
    allowed = record.get("is_pilot_allowed", True)
    if not isinstance(allowed, bool):
        raise HTTPException(status_code=503, detail="Pilot standards data is invalid")
    return StandardCourseRead(
        id=_required_uuid(record, "id"),
        source_id=_required_uuid(record, "source_id"),
        course_key=_required_text(record, "course_key"),
        display_name=_required_text(record, "display_name"),
        source_course_code=_optional_text(record, "source_course_code"),
        grade_band=_optional_text(record, "grade_band"),
        is_pilot_allowed=allowed,
    )


def _catalog_course_read(record: JsonRecord) -> CatalogCourseRead:
    return CatalogCourseRead(
        id=_required_uuid(record, "id"),
        category_id=_required_uuid(record, "category_id"),
        course_key=_required_text(record, "course_key"),
        display_name=_required_text(record, "display_name"),
        source_course_code=_optional_text(record, "source_course_code"),
        grade_band=_optional_text(record, "grade_band"),
    )


def _category_read(record: JsonRecord) -> CatalogCategoryRead:
    return CatalogCategoryRead(
        id=_required_uuid(record, "id"),
        category_key=_required_text(record, "category_key"),
        display_name=_required_text(record, "display_name"),
        category_type=_required_text(record, "category_type"),
        sort_order=_required_int(record, "sort_order"),
    )


def _load_assignment_mapping(
    client: SupabaseRestClient,
    assignment_id: UUID,
) -> JsonRecord | None:
    try:
        rows = _records(
            client.request(
                "GET",
                "assignment_standard_courses",
                params={
                    "teaching_assignment_id": f"eq.{assignment_id}",
                    "select": "teaching_assignment_id,catalog_course_id,mapped_by,mapped_at",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards mapping load")
    if len(rows) > 1:
        raise HTTPException(status_code=503, detail="Pilot standards mapping is invalid")
    return rows[0] if rows else None


def _in_filter(ids: list[UUID]) -> str:
    return f"in.({','.join(str(item) for item in ids)})"


@router.get("/assignment/{assignment_id}", response_model=AssignmentStandardsRead)
def get_assignment_standards(
    assignment_id: UUID,
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AssignmentStandardsRead:
    client = _client(identity, settings)
    _require_assignment(client, identity, assignment_id)
    mapping = _load_assignment_mapping(client, assignment_id)
    if mapping is None or mapping.get("catalog_course_id") is None:
        return AssignmentStandardsRead(
            assignment_id=assignment_id,
            week_start=week_start,
            mapped=False,
        )

    catalog_course_id = _required_uuid(mapping, "catalog_course_id")
    try:
        catalog_course_rows = _records(
            client.request(
                "GET",
                "standard_catalog_courses",
                params={
                    "id": f"eq.{catalog_course_id}",
                    "select": (
                        "id,category_id,course_key,display_name,source_course_code,grade_band"
                    ),
                    "limit": "2",
                },
            )
        )
        link_rows = _records(
            client.request(
                "GET",
                "standard_catalog_course_sources",
                params={
                    "catalog_course_id": f"eq.{catalog_course_id}",
                    "select": "source_course_id,relationship,priority",
                    "order": "priority.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards catalog load")
    if len(catalog_course_rows) != 1:
        raise HTTPException(status_code=503, detail="Standards catalog course is unavailable")
    if not link_rows:
        raise HTTPException(
            status_code=409,
            detail="Standards course has no approved source mapping",
        )

    catalog_course = _catalog_course_read(catalog_course_rows[0])
    try:
        category_rows = _records(
            client.request(
                "GET",
                "standard_catalog_categories",
                params={
                    "id": f"eq.{catalog_course.category_id}",
                    "select": "id,category_key,display_name,category_type,sort_order",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards category load")
    if len(category_rows) != 1:
        raise HTTPException(status_code=503, detail="Standards category is unavailable")
    category = _category_read(category_rows[0])

    source_course_ids = [_required_uuid(row, "source_course_id") for row in link_rows]
    relationship_by_course = {
        _required_uuid(row, "source_course_id"): _required_text(row, "relationship")
        for row in link_rows
    }
    priority_by_course = {
        _required_uuid(row, "source_course_id"): _required_int(row, "priority")
        for row in link_rows
    }

    try:
        source_course_rows = _records(
            client.request(
                "GET",
                "standard_courses",
                params={
                    "id": _in_filter(source_course_ids),
                    "select": (
                        "id,source_id,course_key,display_name,source_course_code,"
                        "grade_band,is_pilot_allowed"
                    ),
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards source-course load")
    if not source_course_rows:
        raise HTTPException(status_code=503, detail="Standards source course is unavailable")

    source_course_by_id = {_required_uuid(row, "id"): row for row in source_course_rows}
    source_ids = sorted(
        {_required_uuid(row, "source_id") for row in source_course_rows},
        key=str,
    )
    try:
        source_rows = _records(
            client.request(
                "GET",
                "standard_sources",
                params={
                    "id": _in_filter(source_ids),
                    "select": (
                        "id,source_key,authority,title,edition,landing_url,approved_snapshot_id"
                    ),
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards source load")

    source_by_id = {_required_uuid(row, "id"): row for row in source_rows}
    approved_snapshot_ids = [
        snapshot_id
        for row in source_rows
        if (snapshot_id := _optional_uuid(row, "approved_snapshot_id")) is not None
    ]
    if not approved_snapshot_ids:
        raise HTTPException(status_code=409, detail="Standards course has no approved snapshot")

    try:
        snapshot_rows = _records(
            client.request(
                "GET",
                "standard_snapshots",
                params={
                    "id": _in_filter(approved_snapshot_ids),
                    "status": "eq.approved",
                    "select": "id,source_id,source_version,retrieved_at,resolved_document_url",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Approved standards snapshot load")
    snapshot_by_source = {
        _required_uuid(row, "source_id"): row for row in snapshot_rows
    }

    valid_course_ids: list[UUID] = []
    valid_snapshot_ids: list[UUID] = []
    for course_id, course_record in source_course_by_id.items():
        source_id = _required_uuid(course_record, "source_id")
        snapshot = snapshot_by_source.get(source_id)
        if snapshot is None:
            continue
        valid_course_ids.append(course_id)
        valid_snapshot_ids.append(_required_uuid(snapshot, "id"))
    if not valid_course_ids:
        raise HTTPException(status_code=409, detail="Standards course has no approved source data")

    try:
        entry_rows = _records(
            client.request(
                "GET",
                "standard_entries",
                params={
                    "course_id": _in_filter(valid_course_ids),
                    "snapshot_id": _in_filter(valid_snapshot_ids),
                    "select": "id,snapshot_id,course_id,code,text,parent_code,strand,sequence",
                },
            )
        )
        selected_rows = _records(
            client.request(
                "GET",
                "weekly_standard_selections",
                params={
                    "teaching_assignment_id": f"eq.{assignment_id}",
                    "week_start": f"eq.{week_start.isoformat()}",
                    "select": "standard_entry_id",
                    "order": "created_at.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Approved standards load")

    sources: list[StandardSourceRead] = []
    for course_id in sorted(valid_course_ids, key=lambda item: priority_by_course.get(item, 100)):
        course_record = source_course_by_id[course_id]
        source_id = _required_uuid(course_record, "source_id")
        source_record = source_by_id.get(source_id)
        snapshot = snapshot_by_source.get(source_id)
        if source_record is None or snapshot is None:
            continue
        sources.append(
            StandardSourceRead(
                id=source_id,
                source_key=_required_text(source_record, "source_key"),
                authority=_required_text(source_record, "authority"),
                title=_required_text(source_record, "title"),
                edition=_required_text(source_record, "edition"),
                landing_url=_required_text(source_record, "landing_url"),
                snapshot_id=_required_uuid(snapshot, "id"),
                source_version=_optional_text(snapshot, "source_version"),
                retrieved_at=_required_text(snapshot, "retrieved_at"),
                resolved_document_url=_required_text(snapshot, "resolved_document_url"),
                relationship=relationship_by_course.get(course_id, "primary"),
            )
        )

    source_priority_by_snapshot: dict[UUID, tuple[int, UUID, StandardSourceRead]] = {}
    for course_id in valid_course_ids:
        course_record = source_course_by_id[course_id]
        source_id = _required_uuid(course_record, "source_id")
        snapshot = snapshot_by_source.get(source_id)
        source_read = next((item for item in sources if item.id == source_id), None)
        if snapshot is not None and source_read is not None:
            source_priority_by_snapshot[_required_uuid(snapshot, "id")] = (
                priority_by_course.get(course_id, 100),
                course_id,
                source_read,
            )

    standards: list[StandardEntryRead] = []
    for row in entry_rows:
        snapshot_id = _required_uuid(row, "snapshot_id")
        source_info = source_priority_by_snapshot.get(snapshot_id)
        if source_info is None:
            continue
        priority, source_course_id, source_read = source_info
        standards.append(
            StandardEntryRead(
                id=_required_uuid(row, "id"),
                code=_required_text(row, "code"),
                text=_required_text(row, "text"),
                parent_code=_optional_text(row, "parent_code"),
                strand=_optional_text(row, "strand"),
                sequence=_required_int(row, "sequence"),
                source_id=source_read.id,
                snapshot_id=snapshot_id,
                authority=source_read.authority,
                source_title=source_read.title,
                relationship=relationship_by_course.get(source_course_id, "primary"),
            )
        )
    standards.sort(
        key=lambda item: (
            source_priority_by_snapshot.get(item.snapshot_id, (100, UUID(int=0), sources[0]))[0]
            if item.snapshot_id is not None and sources
            else 100,
            item.sequence,
            item.code,
        )
    )

    first_course_id = min(valid_course_ids, key=lambda item: priority_by_course.get(item, 100))
    selected_ids = [_required_uuid(row, "standard_entry_id") for row in selected_rows]
    return AssignmentStandardsRead(
        assignment_id=assignment_id,
        week_start=week_start,
        mapped=True,
        source=sources[0] if sources else None,
        sources=sources,
        course=_course_read(source_course_by_id[first_course_id]),
        catalog_category=category,
        catalog_course=catalog_course,
        standards=standards,
        selected_entry_ids=selected_ids,
    )


@router.put(
    "/assignment/{assignment_id}/week/{week_start}",
    response_model=WeeklyStandardsWriteResult,
)
def replace_weekly_standards(
    assignment_id: UUID,
    week_start: date,
    payload: WeeklyStandardsWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklyStandardsWriteResult:
    client = _client(identity, settings)
    _require_assignment(client, identity, assignment_id)
    try:
        result = client.request(
            "POST",
            "rpc/replace_weekly_standard_selections",
            payload={
                "target_assignment_id": str(assignment_id),
                "target_week_start": week_start.isoformat(),
                "target_entry_ids": [str(item) for item in payload.standard_entry_ids],
            },
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Weekly standards selection save")
    if not isinstance(result, int) or isinstance(result, bool):
        raise HTTPException(
            status_code=503,
            detail="Standards selection save returned invalid data",
        )
    return WeeklyStandardsWriteResult(selected_count=result)


@router.get("/admin/sources", response_model=list[AdminSourceRead])
def list_admin_sources(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[AdminSourceRead]:
    client = _client(identity, settings)
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_sources",
                params={
                    "select": (
                        "id,source_key,authority,title,edition,approved_snapshot_id,is_active,"
                        "discovery_status,catalog_category_name"
                    ),
                    "order": "catalog_category_name.asc,title.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards source administration load")
    return [
        AdminSourceRead(
            id=_required_uuid(row, "id"),
            source_key=_required_text(row, "source_key"),
            authority=_required_text(row, "authority"),
            title=_required_text(row, "title"),
            edition=_required_text(row, "edition"),
            approved_snapshot_id=_optional_uuid(row, "approved_snapshot_id"),
            is_active=_required_bool(row, "is_active"),
            discovery_status=_required_text(row, "discovery_status"),
            catalog_category_name=_optional_text(row, "catalog_category_name"),
        )
        for row in rows
    ]
