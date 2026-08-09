from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_platform_admin
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/standards-admin", tags=["standards-administration"])
JsonRecord = dict[str, Any]


class AdminStandardsSourceRead(BaseModel):
    id: UUID
    source_key: str
    family: str
    authority: str
    title: str
    edition: str
    source_kind: str
    provides_standard_entries: bool
    discovery_status: str
    approved_snapshot_id: UUID | None
    approved_snapshot_retrieved_at: str | None
    catalog_category_key: str | None
    catalog_category_name: str | None


class PendingSnapshotRead(BaseModel):
    id: UUID
    source_id: UUID
    source_key: str
    source_title: str
    source_kind: str
    source_version: str | None
    parser_version: str | None
    retrieved_at: str
    resolved_document_url: str
    source_sha256: str
    normalized_sha256: str | None
    parser_status: str | None
    parser_error: str | None
    course_count: int
    standard_entry_count: int


class CatalogRunRead(BaseModel):
    id: UUID
    checked_at: str
    check_month: str | None
    trigger_kind: str
    status: str
    catalog_sha256: str
    discovered_source_count: int
    unchanged_count: int
    changed_count: int
    new_count: int
    missing_count: int
    error_summary: str | None


class CatalogItemRead(BaseModel):
    id: UUID
    source_key: str
    result_state: str
    family: str
    category_name: str | None
    authority: str
    observed_title: str | None
    observed_edition: str | None
    observed_document_url: str | None
    previous_title: str | None
    previous_edition: str | None
    previous_document_url: str | None


class CatalogRunDetailRead(BaseModel):
    run: CatalogRunRead
    items: list[CatalogItemRead] = Field(default_factory=list)


class SnapshotApprovalRead(BaseModel):
    snapshot_id: UUID
    status: str


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Standards administration returned invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=503, detail="Standards administration data is invalid")
    return value.strip()


def _optional_text(record: JsonRecord, key: str) -> str | None:
    value = record.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _uuid(record: JsonRecord, key: str) -> UUID:
    try:
        return UUID(_text(record, key))
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Standards administration data is invalid") from error


def _optional_uuid(record: JsonRecord, key: str) -> UUID | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Standards administration data is invalid") from error


def _int(record: JsonRecord, key: str) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=503, detail="Standards administration data is invalid")
    return value


def _bool(record: JsonRecord, key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise HTTPException(status_code=503, detail="Standards administration data is invalid")
    return value


def _request(
    client: SupabaseRestClient,
    method: str,
    resource: str,
    *,
    params: dict[str, str] | None = None,
    payload: dict[str, object] | list[dict[str, object]] | None = None,
    prefer: str | None = None,
) -> object:
    try:
        return client.request(method, resource, params=params, payload=payload, prefer=prefer)
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise HTTPException(status_code=403, detail="Standards administration access was denied") from error
        raise HTTPException(status_code=503, detail="Standards administration is unavailable") from error


@router.get("/sources", response_model=list[AdminStandardsSourceRead])
def list_admin_sources(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[AdminStandardsSourceRead]:
    client = _client(identity, settings)
    rows = _records(_request(client, "GET", "standard_sources", params={
        "select": (
            "id,source_key,family,authority,title,edition,source_kind,"
            "provides_standard_entries,discovery_status,approved_snapshot_id,"
            "catalog_category_key,catalog_category_name"
        ),
        "order": "family.asc,catalog_category_name.asc,title.asc",
    }))
    snapshot_ids = sorted({str(row.get("approved_snapshot_id")) for row in rows if row.get("approved_snapshot_id")})
    retrieved_by_snapshot: dict[str, str] = {}
    if snapshot_ids:
        snapshots = _records(_request(client, "GET", "standard_snapshots", params={
            "id": f"in.({','.join(snapshot_ids)})",
            "select": "id,retrieved_at",
        }))
        retrieved_by_snapshot = {_text(row, "id"): _text(row, "retrieved_at") for row in snapshots}
    return [
        AdminStandardsSourceRead(
            id=_uuid(row, "id"),
            source_key=_text(row, "source_key"),
            family=_text(row, "family"),
            authority=_text(row, "authority"),
            title=_text(row, "title"),
            edition=_text(row, "edition"),
            source_kind=_text(row, "source_kind"),
            provides_standard_entries=_bool(row, "provides_standard_entries"),
            discovery_status=_text(row, "discovery_status"),
            approved_snapshot_id=_optional_uuid(row, "approved_snapshot_id"),
            approved_snapshot_retrieved_at=retrieved_by_snapshot.get(str(row.get("approved_snapshot_id"))),
            catalog_category_key=_optional_text(row, "catalog_category_key"),
            catalog_category_name=_optional_text(row, "catalog_category_name"),
        )
        for row in rows
    ]


@router.get("/pending-snapshots", response_model=list[PendingSnapshotRead])
def list_pending_snapshots(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[PendingSnapshotRead]:
    client = _client(identity, settings)
    snapshots = _records(_request(client, "GET", "standard_snapshots", params={
        "status": "eq.pending",
        "select": (
            "id,source_id,source_version,parser_version,retrieved_at,"
            "resolved_document_url,source_sha256,normalized_sha256,provenance"
        ),
        "order": "retrieved_at.desc",
    }))
    source_ids = sorted({_text(row, "source_id") for row in snapshots})
    source_by_id: dict[str, JsonRecord] = {}
    if source_ids:
        sources = _records(_request(client, "GET", "standard_sources", params={
            "id": f"in.({','.join(source_ids)})", "select": "id,source_key,title,source_kind",
        }))
        source_by_id = {_text(row, "id"): row for row in sources}
    count_rows = _records(_request(client, "POST", "rpc/platform_admin_standard_snapshot_counts", payload={}))
    counts_by_id = {_text(row, "snapshot_id"): row for row in count_rows}
    results: list[PendingSnapshotRead] = []
    for snapshot in snapshots:
        snapshot_id = _uuid(snapshot, "id")
        source_id = _uuid(snapshot, "source_id")
        source = source_by_id.get(str(source_id))
        counts = counts_by_id.get(str(snapshot_id))
        if source is None:
            raise HTTPException(status_code=503, detail="Pending standards source is missing")
        if counts is None:
            raise HTTPException(status_code=503, detail="Pending standards counts are missing")
        provenance = snapshot.get("provenance")
        provenance_record = provenance if isinstance(provenance, dict) else {}
        parser_status = provenance_record.get("parser_status")
        parser_error = provenance_record.get("parser_error")
        results.append(PendingSnapshotRead(
            id=snapshot_id, source_id=source_id, source_key=_text(source, "source_key"),
            source_title=_text(source, "title"), source_kind=_text(source, "source_kind"),
            source_version=_optional_text(snapshot, "source_version"),
            parser_version=_optional_text(snapshot, "parser_version"), retrieved_at=_text(snapshot, "retrieved_at"),
            resolved_document_url=_text(snapshot, "resolved_document_url"), source_sha256=_text(snapshot, "source_sha256"),
            normalized_sha256=_optional_text(snapshot, "normalized_sha256"),
            parser_status=str(parser_status) if isinstance(parser_status, str) else None,
            parser_error=str(parser_error) if isinstance(parser_error, str) else None,
            course_count=_int(counts, "course_count"), standard_entry_count=_int(counts, "standard_entry_count"),
        ))
    return results


@router.post("/snapshots/{snapshot_id}/approve", response_model=SnapshotApprovalRead)
def approve_snapshot(
    snapshot_id: UUID,
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SnapshotApprovalRead:
    client = _client(identity, settings)
    result = _request(client, "POST", "rpc/approve_standard_snapshot", payload={"target_snapshot_id": str(snapshot_id)})
    if str(result).strip('"') != str(snapshot_id):
        raise HTTPException(status_code=503, detail="Standards snapshot approval returned invalid data")
    return SnapshotApprovalRead(snapshot_id=snapshot_id, status="approved")


@router.get("/catalog-runs", response_model=list[CatalogRunRead])
def list_catalog_runs(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[CatalogRunRead]:
    client = _client(identity, settings)
    rows = _records(_request(client, "GET", "standard_catalog_discovery_runs", params={
        "select": (
            "id,checked_at,check_month,trigger_kind,status,catalog_sha256,"
            "discovered_source_count,unchanged_count,changed_count,new_count,missing_count,error_summary"
        ),
        "order": "checked_at.desc", "limit": "24",
    }))
    return [_catalog_run(row) for row in rows]


@router.get("/catalog-runs/{run_id}", response_model=CatalogRunDetailRead)
def get_catalog_run(
    run_id: UUID,
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CatalogRunDetailRead:
    client = _client(identity, settings)
    run_rows = _records(_request(client, "GET", "standard_catalog_discovery_runs", params={
        "id": f"eq.{run_id}",
        "select": (
            "id,checked_at,check_month,trigger_kind,status,catalog_sha256,"
            "discovered_source_count,unchanged_count,changed_count,new_count,missing_count,error_summary"
        ),
        "limit": "2",
    }))
    if len(run_rows) != 1:
        raise HTTPException(status_code=404, detail="Standards catalog run not found")
    item_rows = _records(_request(client, "GET", "standard_catalog_discovery_items", params={
        "run_id": f"eq.{run_id}",
        "select": (
            "id,source_key,result_state,family,category_name,authority,observed_title,"
            "observed_edition,observed_document_url,previous_title,previous_edition,previous_document_url"
        ),
        "order": "result_state.asc,source_key.asc",
    }))
    return CatalogRunDetailRead(run=_catalog_run(run_rows[0]), items=[
        CatalogItemRead(
            id=_uuid(row, "id"), source_key=_text(row, "source_key"), result_state=_text(row, "result_state"),
            family=_text(row, "family"), category_name=_optional_text(row, "category_name"), authority=_text(row, "authority"),
            observed_title=_optional_text(row, "observed_title"), observed_edition=_optional_text(row, "observed_edition"),
            observed_document_url=_optional_text(row, "observed_document_url"), previous_title=_optional_text(row, "previous_title"),
            previous_edition=_optional_text(row, "previous_edition"), previous_document_url=_optional_text(row, "previous_document_url"),
        ) for row in item_rows
    ])


def _catalog_run(row: JsonRecord) -> CatalogRunRead:
    return CatalogRunRead(
        id=_uuid(row, "id"), checked_at=_text(row, "checked_at"), check_month=_optional_text(row, "check_month"),
        trigger_kind=_text(row, "trigger_kind"), status=_text(row, "status"), catalog_sha256=_text(row, "catalog_sha256"),
        discovered_source_count=_int(row, "discovered_source_count"), unchanged_count=_int(row, "unchanged_count"),
        changed_count=_int(row, "changed_count"), new_count=_int(row, "new_count"), missing_count=_int(row, "missing_count"),
        error_summary=_optional_text(row, "error_summary"),
    )
