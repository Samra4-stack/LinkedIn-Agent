"""
app/database/init_db.py
───────────────────────
Database initialization module.
Creates all tables and seeds default data on first run.
"""

from __future__ import annotations

from app.database.base import Base, engine
from app.database.models import (  # noqa: F401 — ensure all models are imported before create_all
    Draft,
    Post,
    PostAnalytics,
    PostHistory,
    SchedulerJob,
    User,
    UserSettings,
)
from app.utils.logger import get_logger

log = get_logger(__name__)


def init_db() -> None:
    """
    Create all database tables.
    Safe to call multiple times — only creates missing tables.
    """
    log.info("Initializing database...")
    try:
        Base.metadata.create_all(bind=engine)
        log.info("Database tables created successfully")
        _seed_defaults()
    except Exception as e:
        log.error(f"Failed to initialize database: {e}")
        raise


def _seed_defaults() -> None:
    """Seed default settings if not already present."""
    from app.database.base import SessionLocal
    from app.database.crud import get_or_create_settings

    db = SessionLocal()
    try:
        settings_record = get_or_create_settings(db)
        if not settings_record.topics:
            from app.config import settings as app_settings
            settings_record.topics = app_settings.topics_list
            db.commit()
            log.info("Seeded default topics into settings")
    except Exception as e:
        log.warning(f"Could not seed defaults: {e}")
    finally:
        db.close()
