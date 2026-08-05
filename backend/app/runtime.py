from __future__ import annotations

import os
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .auth import load_governed_identity, verify_supabase_access_token
from .main import app
from .settings import get_settings

_PROTECTED_LEGACY_PREFIXES = (
    "/api/v1/admin",
    "/api/v1/assignments",
    "/api/v1/documents",
    "/api/v1/templates",
    "/api/v1/weekly-plan",
)


def _frontend_dist_path() -> Path:
    configured = os.getenv("TPP_FRONTEND_DIST_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "frontend-dist"


@app.middleware("http")
async def protect_legacy_production_routes(request: Request, call_next: object) -> object:
    """Require governed authentication for legacy routes without router dependencies.

    The live workflow routers enforce the same requirement through FastAPI dependencies.
    This production-only layer closes the remaining synthetic, document, and reporting
    surfaces without changing the deterministic unit-test application imported from main.
    """
    if request.url.path.startswith(_PROTECTED_LEGACY_PREFIXES):
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return JSONResponse(
                status_code=401,
                content={"detail": "Bearer access token is required"},
            )
        settings = get_settings()
        try:
            identity = await run_in_threadpool(
                verify_supabase_access_token,
                token.strip(),
                settings,
            )
            await run_in_threadpool(load_governed_identity, identity, settings)
        except PermissionError:
            return JSONResponse(
                status_code=403,
                content={"detail": "Authenticated account is not authorized for this pilot"},
            )
        except RuntimeError:
            return JSONResponse(
                status_code=503,
                content={"detail": "Pilot authorization service is unavailable"},
            )
    return await call_next(request)


frontend_dist = _frontend_dist_path()
if frontend_dist.is_dir():
    # API and health routes are registered before this final catch-all mount.
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
