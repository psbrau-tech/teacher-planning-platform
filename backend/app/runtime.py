from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .auth import load_governed_identity, verify_supabase_access_token
from .main import app
from .role_policy import required_legacy_roles, retired_legacy_replacement
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
async def protect_legacy_production_routes(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Require governed roles and retire synthetic-only production surfaces.

    Live workflow routers enforce equivalent boundaries through FastAPI dependencies.
    This production-only layer protects document/template routes and prevents the
    deterministic synthetic fixtures retained for unit tests from becoming live APIs.
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
            governed = await run_in_threadpool(load_governed_identity, identity, settings)
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

        required = required_legacy_roles(request.url.path)
        if governed.roles.isdisjoint(required):
            return JSONResponse(
                status_code=403,
                content={"detail": "Authenticated role is not authorized for this endpoint"},
            )

        replacement = retired_legacy_replacement(request.url.path)
        if replacement is not None:
            return JSONResponse(
                status_code=410,
                content={
                    "detail": "This synthetic legacy endpoint is retired in production",
                    "replacement": replacement,
                },
            )
    return await call_next(request)


frontend_dist = _frontend_dist_path()
if frontend_dist.is_dir():
    # API and health routes are registered before this final catch-all mount.
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
