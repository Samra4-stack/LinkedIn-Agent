"""
app/database/base.py
────────────────────
SQLAlchemy engine, session factory, and base class configuration.
Supports both synchronous (SQLite dev) and async (PostgreSQL prod) modes.
"""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


# ─── Engine ──────────────────────────────────────────────────
connect_args = {}
if settings.database_url.startswith("sqlite"):
    # Required for SQLite to work with multiple threads (FastAPI uses threads)
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug,       # Log all SQL in debug mode
    pool_pre_ping=True,        # Validate connections before use
)

# Enable WAL mode for SQLite (better concurrent read performance)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ─── Session Factory ─────────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ─── Declarative Base ────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ─── FastAPI Dependency ──────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session and ensure it's closed after use.

    Usage (FastAPI):
        @router.get("/")
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
