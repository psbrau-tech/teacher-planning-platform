from __future__ import annotations

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from .main import app


def _frontend_dist_path() -> Path:
    configured = os.getenv("TPP_FRONTEND_DIST_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "frontend-dist"


frontend_dist = _frontend_dist_path()
if frontend_dist.is_dir():
    # API and health routes are registered before this final catch-all mount.
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
