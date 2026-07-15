"""
app/utils/rate_limiter.py
─────────────────────────
Rate limiting middleware using SlowAPI (backed by slowapi library).
Protects all API endpoints from abuse.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# Global limiter instance — use as a dependency or decorator
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_requests}/{settings.rate_limit_window_seconds}seconds"],
    storage_uri="memory://",
)


def get_limiter() -> Limiter:
    """Return the global limiter instance."""
    return limiter
