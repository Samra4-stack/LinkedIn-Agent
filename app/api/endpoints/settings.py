"""
app/api/endpoints/settings.py
──────────────────────────────
GET /settings    — Get current settings.
PUT /settings    — Update settings.
GET /settings/memory — Get agent memory state.
POST /settings/memory/reset — Reset memory (use carefully).
"""



from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.memory_agent import MemoryAgent
from app.database import crud
from app.database.base import get_db
from app.models.schemas import SettingsSchema, SuccessResponse, UpdateSettingsRequest
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


@router.get(
    "/settings",
    response_model=SettingsSchema,
    summary="Get current settings",
    description="Get all configurable agent settings.",
    tags=["Settings"],
)
async def get_settings(db: Session = Depends(get_db)) -> SettingsSchema:
    """Get current settings."""
    log.info("GET /settings")
    settings_record = crud.get_or_create_settings(db)
    # Populate topics from config if empty
    if not settings_record.topics:
        from app.config import settings as app_settings
        settings_record.topics = app_settings.topics_list
    return SettingsSchema.model_validate(settings_record)


@router.put(
    "/settings",
    response_model=SettingsSchema,
    summary="Update settings",
    description="""
    Update agent settings. All fields are optional — only provide what you want to change.

    **Scheduler settings:**
    - `scheduler_hour` / `scheduler_minute` — Daily generation time
    - `scheduler_timezone` — IANA timezone (e.g., "Asia/Karachi")
    - `scheduler_enabled` — Enable/disable auto-generation

    **Content settings:**
    - `topics` — List of topics to cycle through
    - `preferred_hashtags` — Hashtag categories to prefer
    - `writing_style` — professional | casual | storytelling | educational
    - `preferred_image_provider` — unsplash | pexels | pixabay | dalle
    - `preferred_ai_provider` — openai | gemini
    - `post_language` — Language for generated content
    """,
    tags=["Settings"],
)
async def update_settings(
    payload: UpdateSettingsRequest,
    db: Session = Depends(get_db),
) -> SettingsSchema:
    """Update agent settings."""
    log.info(f"PUT /settings | fields={[k for k,v in payload.model_dump().items() if v is not None]}")

    settings_record = crud.get_or_create_settings(db)
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}

    if updates:
        settings_record = crud.update_settings(db, settings_record, **updates)

        # Sync memory with new preferences
        memory_agent = MemoryAgent(db=db)
        memory_agent.update_preferences(
            hashtags=payload.preferred_hashtags,
            style=payload.writing_style,
        )

        # Reschedule if time changed
        if payload.scheduler_hour is not None or payload.scheduler_minute is not None:
            from app.services.scheduler_service import scheduler_service
            scheduler_service.reschedule(
                hour=settings_record.scheduler_hour,
                minute=settings_record.scheduler_minute,
                timezone=settings_record.scheduler_timezone,
            )
            log.info(f"Scheduler rescheduled to {settings_record.scheduler_hour:02d}:{settings_record.scheduler_minute:02d}")

    return SettingsSchema.model_validate(settings_record)


@router.get(
    "/settings/memory",
    response_model=Dict[str, Any],
    summary="Get agent memory snapshot",
    description="View the agent's complete memory state (topics used, preferences, statistics).",
    tags=["Settings"],
)
async def get_memory(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get agent memory snapshot."""
    memory_agent = MemoryAgent(db=db)
    return memory_agent.get_full_memory_snapshot()


@router.post(
    "/settings/memory/reset",
    response_model=SuccessResponse,
    summary="Reset agent memory",
    description="""
    ⚠️ **Warning**: This resets all agent memory including topic history,
    content hashes, and preferences. Use with caution.

    The database history is preserved; only the in-memory JSON store is reset.
    """,
    tags=["Settings"],
)
async def reset_memory() -> SuccessResponse:
    """Reset the agent memory store."""
    from app.memory.memory_store import memory_store
    memory_store.reset()
    log.warning("Memory store reset via API")
    return SuccessResponse(
        message="Agent memory reset successfully. Topics and preferences have been cleared."
    )
