from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .auth import AuthenticatedTeacher, require_teacher
from .document_service import DEFAULT_TEMPLATE_PATH, generate_anniston_hqi_packet
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError
from .week_dates import require_monday

router = APIRouter(prefix="/api/v1/teacher-submissions", tags=["teacher"])


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Submitted packet data is unavailable")
    return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Authenticated access token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


@router.get("/{assignment_id}/completed-packet")
def completed_packet(
    assignment_id: str,
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Render the teacher's own latest immutable completed packet for one Monday-starting week."""
    require_monday(week_start)
    try:
        rows = _records(
            _client(identity, settings).request(
                "POST",
                "rpc/teacher_completed_weekly_submission_document",
                payload={
                    "target_assignment_id": assignment_id,
                    "target_week_start": week_start.isoformat(),
                },
            )
        )
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise HTTPException(status_code=403, detail="Completed packet access is not authorized") from error
        raise HTTPException(status_code=503, detail="Completed packet is unavailable") from error

    if not rows:
        raise HTTPException(status_code=404, detail="Completed weekly packet was not found")
    source_data = rows[0].get("source_data")
    if not isinstance(source_data, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in source_data.items()
    ):
        raise HTTPException(status_code=503, detail="Completed packet source data is invalid")
    if not DEFAULT_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=503, detail="The approved planning PDF template is unavailable")
    try:
        packet, documents = generate_anniston_hqi_packet(cast(dict[str, str], source_data))
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Completed packet PDF could not be generated") from error

    revision = rows[0].get("revision")
    return StreamingResponse(
        BytesIO(packet),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="completed-weekly-packet-{week_start.isoformat()}.pdf"',
            "X-TPP-Submission-Kind": "completed_packet",
            "X-TPP-Submitted-Revision": str(revision) if isinstance(revision, int) else "",
            "X-TPP-Document-Count": str(len(documents)),
        },
    )
