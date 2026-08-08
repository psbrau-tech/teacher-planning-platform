from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import AuthenticatedTeacher, require_platform_admin
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/act-reference-admin", tags=["act-reference-administration"])
JsonRecord = dict[str, Any]


class ActReferenceSnapshotRead(BaseModel):
    id: UUID
    source_id: UUID
    source_key: str
    source_title: str
    source_type: str
    source_document_url: str
    source_edition: str | None
    source_effective_date: str | None
    retrieved_at: str
    parser_version: str
    source_sha256: str
    normalized_sha256: str
    entry_count: int
    benchmark_count: int
    status: str


class ActReferenceApprovalRead(BaseModel):
    snapshot_id: UUID
    source_id: UUID
    status: str
    changed: bool


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise HTTPException(
            status_code=503, detail="ACT reference administration returned invalid data"
        )
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=503, detail="ACT reference administration data is invalid")
    return value.strip()


def _optional_text(record: JsonRecord, key: str) -> str | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=503, detail="ACT reference administration data is invalid")
    return value.strip()


def _uuid(record: JsonRecord, key: str) -> UUID:
    try:
        return UUID(_text(record, key))
    except ValueError as error:
        raise HTTPException(
            status_code=503, detail="ACT reference administration data is invalid"
        ) from error


@router.get("/pending", response_model=list[ActReferenceSnapshotRead])
def list_pending_act_reference_snapshots(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ActReferenceSnapshotRead]:
    client = _client(identity, settings)
    try:
        snapshots = _records(
            client.request(
                "GET",
                "act_reference_snapshots",
                params={
                    "status": "eq.pending",
                    "select": (
                        "id,source_id,retrieved_at,parser_version,source_sha256,"
                        "normalized_sha256,status"
                    ),
                    "order": "retrieved_at.desc",
                },
            )
        )
    except SupabaseRestError as error:
        raise HTTPException(
            status_code=503, detail="ACT pending snapshots are unavailable"
        ) from error

    output: list[ActReferenceSnapshotRead] = []
    for snapshot in snapshots:
        source_id = _uuid(snapshot, "source_id")
        snapshot_id = _uuid(snapshot, "id")
        try:
            source_rows = _records(
                client.request(
                    "GET",
                    "act_reference_sources",
                    params={
                        "id": f"eq.{source_id}",
                        "select": (
                            "source_key,title,source_type,document_url,edition,effective_date"
                        ),
                        "limit": "2",
                    },
                )
            )
            entry_rows = _records(
                client.request(
                    "GET",
                    "act_reference_entries",
                    params={
                        "snapshot_id": f"eq.{snapshot_id}",
                        "select": "id",
                    },
                )
            )
            benchmark_rows = _records(
                client.request(
                    "GET",
                    "act_readiness_benchmarks",
                    params={
                        "snapshot_id": f"eq.{snapshot_id}",
                        "select": "id",
                    },
                )
            )
        except SupabaseRestError as error:
            raise HTTPException(
                status_code=503, detail="ACT pending snapshot detail is unavailable"
            ) from error
        if len(source_rows) != 1:
            raise HTTPException(status_code=503, detail="ACT reference source is unavailable")
        source = source_rows[0]
        output.append(
            ActReferenceSnapshotRead(
                id=snapshot_id,
                source_id=source_id,
                source_key=_text(source, "source_key"),
                source_title=_text(source, "title"),
                source_type=_text(source, "source_type"),
                source_document_url=_text(source, "document_url"),
                source_edition=_optional_text(source, "edition"),
                source_effective_date=_optional_text(source, "effective_date"),
                retrieved_at=_text(snapshot, "retrieved_at"),
                parser_version=_text(snapshot, "parser_version"),
                source_sha256=_text(snapshot, "source_sha256"),
                normalized_sha256=_text(snapshot, "normalized_sha256"),
                entry_count=len(entry_rows),
                benchmark_count=len(benchmark_rows),
                status=_text(snapshot, "status"),
            )
        )
    return output


@router.post("/snapshots/{snapshot_id}/approve", response_model=ActReferenceApprovalRead)
def approve_act_reference_snapshot(
    snapshot_id: UUID,
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActReferenceApprovalRead:
    client = _client(identity, settings)
    try:
        payload = client.request(
            "POST",
            "rpc/approve_act_reference_snapshot",
            payload={"target_snapshot_id": str(snapshot_id)},
        )
    except SupabaseRestError as error:
        if error.status_code in {400, 409, 422}:
            raise HTTPException(
                status_code=409, detail="ACT reference snapshot approval was rejected"
            ) from error
        raise HTTPException(
            status_code=503, detail="ACT reference snapshot approval is unavailable"
        ) from error
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=503, detail="ACT reference snapshot approval returned invalid data"
        )
    record = cast(JsonRecord, payload)
    changed = record.get("changed")
    if not isinstance(changed, bool):
        raise HTTPException(
            status_code=503, detail="ACT reference snapshot approval returned invalid data"
        )
    return ActReferenceApprovalRead(
        snapshot_id=_uuid(record, "snapshot_id"),
        source_id=_uuid(record, "source_id"),
        status=_text(record, "status"),
        changed=changed,
    )
