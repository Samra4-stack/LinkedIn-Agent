"""
app/api/router.py
──────────────────
Central API router that aggregates all endpoint routers.
Registers all routes under /api/v1 prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints import (
    analytics,
    edit,
    generate,
    history,
    preview,
    publish,
    regenerate,
    schedule,
    settings,
)

api_router = APIRouter(prefix="/api/v1")

# ── Core workflow endpoints ──────────────────────────────────
api_router.include_router(generate.router)
api_router.include_router(preview.router)
api_router.include_router(publish.router)
api_router.include_router(edit.router)
api_router.include_router(regenerate.router)

# ── Management endpoints ─────────────────────────────────────
api_router.include_router(schedule.router)
api_router.include_router(history.router)
api_router.include_router(analytics.router)
api_router.include_router(settings.router)
