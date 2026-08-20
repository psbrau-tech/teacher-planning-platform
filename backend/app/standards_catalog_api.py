from __future__ import annotations

from typing import Annotated, Any, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/standards", tags=["standards-catalog"])
JsonRecord = dict[str, Any]


class CatalogCategoryRead(BaseModel):
    id: UUID
    category_key: str
    display_name: str
    category_type: str
    sort_order: int


class CatalogCourseRead(BaseModel):
    id: UUID
    category_id: UUID
    course_key: str
    display_name: str
    source_course_code: str | None
    grade_band: str | None


class AssignmentCatalogMappingRead(BaseModel):
    assignment_id: UUID
    mapped: bool
    category: CatalogCategoryRead | None = None
    course: CatalogCourseRead | None = None
    warning_required_for_change: bool = False
    weekly_plan_count: int = 0
    validated_week_count: int = 0


class AssignmentCatalogMappingWrite(BaseModel):
    catalog_course_id: UUID
    confirm_existing_plans: bool = False


class AssignmentCatalogMappingWriteResult(BaseModel):
    assignment_id: UUID
    changed: bool
    warning_required: bool
    open_selection_count_cleared: int
    validated_week_count_preserved: int
    category: CatalogCategoryRead
    course: CatalogCourseRead


class ProficiencyScaleRead(BaseModel):
    standard_code: str
    standard_text: str
    literacy_type: str | None = None
    focus_area: str | None = None
    category: str | None = None
    levels: dict[str, str] = Field(default_factory=dict)


class ProficiencyGradeRead(BaseModel):
    grade_band: str
    available: bool
    authority: str | None = None
    source_title: str | None = None
    source_version: str | None = None
    retrieved_at: str | None = None
    landing_url: str | None = None
    resolved_document_url: str | None = None
    scales: list[ProficiencyScaleRead] = Field(default_factory=list)


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Standards catalog returned invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _required_text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=503, detail="Standards catalog data is invalid")
    return value.strip()


def _optional_text(record: JsonRecord, key: str) -> str | None:
    value = record.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _required_uuid(record: JsonRecord, key: str) -> UUID:
    try:
        return UUID(_required_text(record, key))
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Standards catalog data is invalid") from error


def _required_int(record: JsonRecord, key: str) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=503, detail="Standards catalog data is invalid")
    return value


def _levels(record: JsonRecord) -> dict[str, str]:
    value = record.get("levels")
    if not isinstance(value, dict):
        raise HTTPException(status_code=503, detail="Proficiency scale data is invalid")
    levels: dict[str, str] = {}
    for key, text in value.items():
        if isinstance(key, str) and isinstance(text, str) and text.strip():
            levels[key] = text.strip()
    if not all(level in levels for level in ("4.0", "3.0", "2.0")):
        raise HTTPException(status_code=503, detail="Proficiency scale data is incomplete")
    return levels


def _raise_data_error(error: SupabaseRestError, operation: str) -> NoReturn:
    message = str(error).lower()
    if error.status_code in {401, 403}:
        raise HTTPException(
            status_code=403,
            detail="Standards catalog access was denied",
        ) from error
    if "explicit confirmation" in message:
        raise HTTPException(
            status_code=409,
            detail=(
                "Changing this standards mapping requires confirmation because weekly "
                "planning already exists. Validated history will remain unchanged."
            ),
        ) from error
    if error.status_code in {400, 409, 422}:
        raise HTTPException(status_code=409, detail=f"{operation} was rejected") from error
    raise HTTPException(
        status_code=503,
        detail="Standards catalog service is unavailable",
    ) from error


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _require_owned_assignment(
    client: SupabaseRestClient,
    identity: AuthenticatedTeacher,
    assignment_id: UUID,
) -> None:
    try:
        rows = _records(
            client.request(
                "GET",
                "teaching_assignments",
                params={
                    "id": f"eq.{assignment_id}",
                    "teacher_id": f"eq.{identity.subject}",
                    "select": "id",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Teaching assignment load")
    if len(rows) != 1:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")


def _category_read(record: JsonRecord) -> CatalogCategoryRead:
    return CatalogCategoryRead(
        id=_required_uuid(record, "id"),
        category_key=_required_text(record, "category_key"),
        display_name=_required_text(record, "display_name"),
        category_type=_required_text(record, "category_type"),
        sort_order=_required_int(record, "sort_order"),
    )


def _course_read(record: JsonRecord) -> CatalogCourseRead:
    return CatalogCourseRead(
        id=_required_uuid(record, "id"),
        category_id=_required_uuid(record, "category_id"),
        course_key=_required_text(record, "course_key"),
        display_name=_required_text(record, "display_name"),
        source_course_code=_optional_text(record, "source_course_code"),
        grade_band=_optional_text(record, "grade_band"),
    )


def _load_category(
    client: SupabaseRestClient,
    category_id: UUID,
) -> CatalogCategoryRead:
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_catalog_categories",
                params={
                    "id": f"eq.{category_id}",
                    "select": "id,category_key,display_name,category_type,sort_order",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards category load")
    if len(rows) != 1:
        raise HTTPException(status_code=503, detail="Standards category is unavailable")
    return _category_read(rows[0])


def _load_course(
    client: SupabaseRestClient,
    course_id: UUID,
) -> CatalogCourseRead:
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_catalog_courses",
                params={
                    "id": f"eq.{course_id}",
                    "select": (
                        "id,category_id,course_key,display_name,source_course_code,grade_band"
                    ),
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards course load")
    if len(rows) != 1:
        raise HTTPException(status_code=503, detail="Standards course is unavailable")
    return _course_read(rows[0])


@router.get("/catalog/categories", response_model=list[CatalogCategoryRead])
def list_catalog_categories(
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[CatalogCategoryRead]:
    client = _client(identity, settings)
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_catalog_categories",
                params={
                    "is_active": "eq.true",
                    "select": "id,category_key,display_name,category_type,sort_order",
                    "order": "sort_order.asc,display_name.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards category list")
    return [_category_read(row) for row in rows]


@router.get(
    "/catalog/categories/{category_id}/courses",
    response_model=list[CatalogCourseRead],
)
def list_catalog_courses(
    category_id: UUID,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[CatalogCourseRead]:
    client = _client(identity, settings)
    try:
        rows = _records(
            client.request(
                "GET",
                "standard_catalog_courses",
                params={
                    "category_id": f"eq.{category_id}",
                    "is_active": "eq.true",
                    "select": (
                        "id,category_id,course_key,display_name,source_course_code,grade_band"
                    ),
                    "order": "display_name.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards course list")
    return [_course_read(row) for row in rows]


@router.get(
    "/proficiency/grade/{grade_band}",
    response_model=ProficiencyGradeRead,
)
def get_ela_proficiency_grade(
    grade_band: int,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProficiencyGradeRead:
    if grade_band < 6 or grade_band > 12:
        raise HTTPException(status_code=404, detail="ELA proficiency scales are available for grades 6-12")

    client = _client(identity, settings)
    source_key = f"alabama_ela_proficiency_grade_{grade_band}"
    try:
        source_rows = _records(
            client.request(
                "GET",
                "standard_sources",
                params={
                    "source_key": f"eq.{source_key}",
                    "source_kind": "eq.proficiency_scale",
                    "is_active": "eq.true",
                    "select": "id,authority,title,landing_url,approved_snapshot_id",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Proficiency source load")

    if len(source_rows) != 1:
        return ProficiencyGradeRead(grade_band=str(grade_band), available=False)
    source = source_rows[0]
    snapshot_id = _optional_text(source, "approved_snapshot_id")
    if snapshot_id is None:
        return ProficiencyGradeRead(
            grade_band=str(grade_band),
            available=False,
            authority=_required_text(source, "authority"),
            source_title=_required_text(source, "title"),
            landing_url=_required_text(source, "landing_url"),
        )

    try:
        snapshot_rows = _records(
            client.request(
                "GET",
                "standard_snapshots",
                params={
                    "id": f"eq.{snapshot_id}",
                    "status": "eq.approved",
                    "select": "id,source_version,retrieved_at,resolved_document_url",
                    "limit": "2",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Approved proficiency snapshot load")
    if len(snapshot_rows) != 1:
        return ProficiencyGradeRead(
            grade_band=str(grade_band),
            available=False,
            authority=_required_text(source, "authority"),
            source_title=_required_text(source, "title"),
            landing_url=_required_text(source, "landing_url"),
        )
    snapshot = snapshot_rows[0]

    try:
        scale_rows = _records(
            client.request(
                "GET",
                "standard_proficiency_scales",
                params={
                    "snapshot_id": f"eq.{snapshot_id}",
                    "grade_band": f"eq.{grade_band}",
                    "select": (
                        "standard_code,standard_text,literacy_type,focus_area,category,levels"
                    ),
                    "order": "standard_code.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Approved proficiency scales load")

    return ProficiencyGradeRead(
        grade_band=str(grade_band),
        available=bool(scale_rows),
        authority=_required_text(source, "authority"),
        source_title=_required_text(source, "title"),
        source_version=_optional_text(snapshot, "source_version"),
        retrieved_at=_required_text(snapshot, "retrieved_at"),
        landing_url=_required_text(source, "landing_url"),
        resolved_document_url=_required_text(snapshot, "resolved_document_url"),
        scales=[
            ProficiencyScaleRead(
                standard_code=_required_text(row, "standard_code"),
                standard_text=_required_text(row, "standard_text"),
                literacy_type=_optional_text(row, "literacy_type"),
                focus_area=_optional_text(row, "focus_area"),
                category=_optional_text(row, "category"),
                levels=_levels(row),
            )
            for row in scale_rows
        ],
    )


@router.get(
    "/assignment/{assignment_id}/mapping",
    response_model=AssignmentCatalogMappingRead,
)
def get_assignment_catalog_mapping(
    assignment_id: UUID,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AssignmentCatalogMappingRead:
    client = _client(identity, settings)
    _require_owned_assignment(client, identity, assignment_id)
    try:
        mapping_rows = _records(
            client.request(
                "GET",
                "assignment_standard_courses",
                params={
                    "teaching_assignment_id": f"eq.{assignment_id}",
                    "select": "catalog_course_id",
                    "limit": "2",
                },
            )
        )
        plan_rows = _records(
            client.request(
                "GET",
                "weekly_plan_snapshots",
                params={
                    "teaching_assignment_id": f"eq.{assignment_id}",
                    "select": "id",
                },
            )
        )
        validation_rows = _records(
            client.request(
                "GET",
                "friday_validation_snapshots",
                params={
                    "teaching_assignment_id": f"eq.{assignment_id}",
                    "select": "id",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards mapping load")
    if len(mapping_rows) > 1:
        raise HTTPException(status_code=503, detail="Standards mapping is invalid")
    if not mapping_rows or mapping_rows[0].get("catalog_course_id") is None:
        return AssignmentCatalogMappingRead(
            assignment_id=assignment_id,
            mapped=False,
            weekly_plan_count=len(plan_rows),
            validated_week_count=len(validation_rows),
        )

    course_id = _required_uuid(mapping_rows[0], "catalog_course_id")
    course = _load_course(client, course_id)
    category = _load_category(client, course.category_id)
    return AssignmentCatalogMappingRead(
        assignment_id=assignment_id,
        mapped=True,
        category=category,
        course=course,
        warning_required_for_change=len(plan_rows) > 0,
        weekly_plan_count=len(plan_rows),
        validated_week_count=len(validation_rows),
    )


@router.put(
    "/assignment/{assignment_id}/mapping",
    response_model=AssignmentCatalogMappingWriteResult,
)
def set_assignment_catalog_mapping(
    assignment_id: UUID,
    payload: AssignmentCatalogMappingWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AssignmentCatalogMappingWriteResult:
    client = _client(identity, settings)
    _require_owned_assignment(client, identity, assignment_id)
    try:
        result = client.request(
            "POST",
            "rpc/set_assignment_standard_catalog_course",
            payload={
                "target_assignment_id": str(assignment_id),
                "target_catalog_course_id": str(payload.catalog_course_id),
                "confirm_existing_plans": payload.confirm_existing_plans,
            },
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Standards mapping save")
    if not isinstance(result, dict):
        raise HTTPException(status_code=503, detail="Standards mapping save returned invalid data")
    record = cast(JsonRecord, result)
    changed = record.get("changed")
    warning_required = record.get("warning_required")
    if not isinstance(changed, bool) or not isinstance(warning_required, bool):
        raise HTTPException(status_code=503, detail="Standards mapping save returned invalid data")

    course = _load_course(client, payload.catalog_course_id)
    category = _load_category(client, course.category_id)
    return AssignmentCatalogMappingWriteResult(
        assignment_id=assignment_id,
        changed=changed,
        warning_required=warning_required,
        open_selection_count_cleared=_required_int(record, "open_selection_count_cleared"),
        validated_week_count_preserved=_required_int(
            record,
            "validated_week_count_preserved",
        ),
        category=category,
        course=course,
    )
