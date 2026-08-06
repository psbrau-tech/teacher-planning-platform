from typing import Annotated

from fastapi import APIRouter, Depends

from .readiness import evaluate_runtime_readiness
from .settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])


@router.get("/readiness")
def runtime_readiness(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    readiness = evaluate_runtime_readiness(settings)
    return {
        "environment": readiness.environment,
        "public_base_url": readiness.public_base_url,
        "data_boundary": readiness.data_boundary,
        "supabase_configured": readiness.supabase_configured,
        "pilot_access_configured": readiness.pilot_access_configured,
        "privileged_runtime_credentials_absent": (
            readiness.privileged_runtime_credentials_absent
        ),
        "core_ready": readiness.core_ready,
    }
