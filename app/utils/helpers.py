"""
app/utils/helpers.py
────────────────────
General-purpose helper utilities used across the application.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pytz import timezone as pytz_timezone


def slugify(text: str) -> str:
    """
    Convert text to URL-safe slug.

    Example:
        slugify("Hello World! 123") → "hello-world-123"
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def truncate_text(text: str, max_length: int = 150, suffix: str = "...") -> str:
    """
    Truncate text to max_length, appending suffix if truncated.

    Example:
        truncate_text("Hello World", 8) → "Hello..."
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def now_utc() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def now_local(tz_name: str = "Asia/Karachi") -> datetime:
    """Return current datetime in the specified timezone."""
    tz = pytz_timezone(tz_name)
    return datetime.now(tz)


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """Format a datetime object to string."""
    return dt.strftime(fmt)


def compute_hash(text: str) -> str:
    """
    Compute SHA-256 hash of text (used for duplicate detection).

    Args:
        text: Input string
    Returns:
        Hex digest string
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_hashtags(text: str) -> List[str]:
    """
    Extract hashtags from post text.

    Example:
        extract_hashtags("Hello #Python #AI world") → ["#Python", "#AI"]
    """
    return re.findall(r"#\w+", text)


def clean_hashtags(hashtags: List[str]) -> List[str]:
    """
    Normalize hashtag list: remove duplicates, ensure # prefix,
    remove spaces, lowercase everything.
    """
    cleaned = []
    seen = set()
    for tag in hashtags:
        tag = tag.strip()
        if not tag.startswith("#"):
            tag = f"#{tag}"
        tag = re.sub(r"\s+", "", tag)
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            cleaned.append(tag)
    return cleaned


def is_valid_url(url: str) -> bool:
    """
    Check whether a URL is syntactically valid.

    Args:
        url: URL string to validate
    Returns:
        True if valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def build_post_preview(post_data: Dict[str, Any]) -> str:
    """
    Build a human-readable text preview of a LinkedIn post.

    Args:
        post_data: Dictionary containing post fields
    Returns:
        Formatted preview string
    """
    lines = [
        "═" * 60,
        f"📌 TOPIC:    {post_data.get('topic', 'N/A')}",
        f"🕐 SCHEDULED: {post_data.get('scheduled_time', 'N/A')}",
        "═" * 60,
        "",
        "📝 FULL POST:",
        "─" * 60,
        post_data.get("content", ""),
        "",
        "─" * 60,
        f"🖼️  IMAGE: {post_data.get('image_url', 'No image')}",
        "",
        "🔗 LINKS:",
    ]
    for link in post_data.get("links", []):
        lines.append(f"   • {link}")

    lines += [
        "",
        "🏷️  HASHTAGS:",
        "   " + " ".join(post_data.get("hashtags", [])),
        "═" * 60,
    ]
    return "\n".join(lines)


def calculate_engagement_rate(
    likes: int,
    comments: int,
    shares: int,
    views: int,
) -> Optional[float]:
    """
    Calculate LinkedIn post engagement rate.

    Formula: (likes + comments + shares) / views * 100

    Returns:
        Engagement rate as percentage, or None if views is 0
    """
    if views == 0:
        return None
    return round((likes + comments + shares) / views * 100, 2)


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """
    Sanitize user-provided text input.
    - Strips leading/trailing whitespace
    - Removes null bytes
    - Enforces max length
    """
    text = text.replace("\x00", "").strip()
    return text[:max_length]


def chunk_list(lst: List[Any], size: int) -> List[List[Any]]:
    """Split a list into chunks of given size."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]
