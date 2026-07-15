"""
app/memory/memory_store.py
──────────────────────────
Persistent memory store for the LinkedIn AI Agent.
Combines JSON file storage (fast reads) with database queries.

Tracks:
- Topics already posted (to avoid repetition)
- Writing style preferences
- Preferred hashtags
- Posting schedule history
- Favorite topics
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

MEMORY_VERSION = "1.0"


class MemoryStore:
    """
    Hybrid memory store: JSON file + SQLite database.

    JSON file provides fast access to frequently-read data.
    Database provides persistent history and queryable records.
    """

    def __init__(self, file_path: Optional[str] = None) -> None:
        self.file_path = Path(file_path or settings.memory_file_path)
        self._ensure_directory()
        self._memory: Dict[str, Any] = self._load()

    def _ensure_directory(self) -> None:
        """Create the data directory if it doesn't exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        """Load memory from JSON file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                log.debug(f"Memory loaded | file={self.file_path}")
                return data
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"Could not load memory file: {e}. Starting fresh.")

        return self._default_memory()

    def _save(self) -> None:
        """Persist memory to JSON file."""
        self._memory["last_updated"] = datetime.now(timezone.utc).isoformat()
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._memory, f, indent=2, ensure_ascii=False)
        except OSError as e:
            log.error(f"Could not save memory: {e}")

    def _default_memory(self) -> Dict[str, Any]:
        """Return default memory structure."""
        return {
            "version": MEMORY_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "topics_used": [],           # List of {"topic": str, "used_at": ISO, "angle": str}
            "content_hashes": [],        # List of hashes to detect duplicates
            "preferred_hashtags": [],    # User's favorite hashtags
            "writing_style": "professional",
            "post_language": "English",
            "posting_times": [],         # History of when posts were generated
            "favorite_topics": [],       # User's explicitly marked favorite topics
            "avoided_topics": [],        # Topics the user wants to skip
            "statistics": {
                "total_generated": 0,
                "total_published": 0,
                "total_cancelled": 0,
                "last_generated_at": None,
                "last_published_at": None,
            },
        }

    # ── Topic Memory ────────────────────────────────────────

    def record_topic_used(self, topic: str, angle: str = "") -> None:
        """Record that a topic was used for generation."""
        entry = {
            "topic": topic,
            "angle": angle,
            "used_at": datetime.now(timezone.utc).isoformat(),
        }
        self._memory["topics_used"].append(entry)

        # Trim history to max_history_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.max_history_days)
        self._memory["topics_used"] = [
            e for e in self._memory["topics_used"]
            if datetime.fromisoformat(e["used_at"]) > cutoff
        ]

        self._memory["statistics"]["total_generated"] = (
            self._memory["statistics"].get("total_generated", 0) + 1
        )
        self._memory["statistics"]["last_generated_at"] = datetime.now(timezone.utc).isoformat()

        self._save()
        log.info(f"Recorded topic usage | topic={topic}")

    def get_recent_topics(self, days: int = 30) -> List[str]:
        """
        Return topics used in the last N days.
        Used to avoid content repetition.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return [
            e["topic"]
            for e in self._memory["topics_used"]
            if datetime.fromisoformat(e["used_at"]) > cutoff
        ]

    def get_recent_angles(self, topic: str, days: int = 90) -> List[str]:
        """Return recently covered angles for a specific topic."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return [
            e["angle"]
            for e in self._memory["topics_used"]
            if e["topic"] == topic
            and e.get("angle")
            and datetime.fromisoformat(e["used_at"]) > cutoff
        ]

    def is_topic_overused(self, topic: str, min_gap_days: int = 7) -> bool:
        """
        Check if a topic was used too recently.

        Args:
            topic: Topic to check
            min_gap_days: Minimum days between same-topic posts

        Returns:
            True if topic was used within min_gap_days
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=min_gap_days)
        return any(
            e["topic"] == topic and datetime.fromisoformat(e["used_at"]) > cutoff
            for e in self._memory["topics_used"]
        )

    def select_next_topic(self, available_topics: List[str]) -> str:
        """
        Select the next topic to post about.
        Prioritizes:
        1. Favorite topics not recently used
        2. Topics not used in the last 7 days
        3. Least recently used topic overall

        Args:
            available_topics: All configured topics

        Returns:
            Selected topic string
        """
        if not available_topics:
            return "Artificial Intelligence"

        recent = set(self.get_recent_topics(days=7))
        favorites = set(self._memory.get("favorite_topics", []))
        avoided = set(self._memory.get("avoided_topics", []))

        # Filter out avoided topics
        candidates = [t for t in available_topics if t not in avoided]
        if not candidates:
            candidates = available_topics

        # Prioritize favorites not recently used
        fresh_favorites = [t for t in candidates if t in favorites and t not in recent]
        if fresh_favorites:
            return fresh_favorites[0]

        # Topics not used in last 7 days
        fresh = [t for t in candidates if t not in recent]
        if fresh:
            return fresh[0]

        # All topics recently used — pick least recently used
        topic_last_used: Dict[str, str] = {}
        for entry in self._memory["topics_used"]:
            topic = entry["topic"]
            if topic in candidates:
                if topic not in topic_last_used or entry["used_at"] > topic_last_used[topic]:
                    topic_last_used[topic] = entry["used_at"]

        if topic_last_used:
            return min(topic_last_used, key=lambda t: topic_last_used[t])

        return candidates[0]

    # ── Content Hash Memory ─────────────────────────────────

    def record_content_hash(self, content_hash: str) -> None:
        """Record a content hash to prevent exact duplicates."""
        if content_hash not in self._memory["content_hashes"]:
            self._memory["content_hashes"].append(content_hash)
            # Keep only last 1000 hashes
            self._memory["content_hashes"] = self._memory["content_hashes"][-1000:]
            self._save()

    def is_duplicate_content(self, content_hash: str) -> bool:
        """Check if this exact content was generated before."""
        return content_hash in self._memory["content_hashes"]

    # ── Style Memory ────────────────────────────────────────

    def update_writing_style(self, style: str) -> None:
        """Update the preferred writing style."""
        self._memory["writing_style"] = style
        self._save()

    def get_writing_style(self) -> str:
        return self._memory.get("writing_style", "professional")

    # ── Hashtag Memory ──────────────────────────────────────

    def update_preferred_hashtags(self, hashtags: List[str]) -> None:
        """Update preferred hashtag list."""
        self._memory["preferred_hashtags"] = hashtags
        self._save()

    def get_preferred_hashtags(self) -> List[str]:
        return self._memory.get("preferred_hashtags", [])

    # ── Favorites Management ────────────────────────────────

    def add_favorite_topic(self, topic: str) -> None:
        if topic not in self._memory["favorite_topics"]:
            self._memory["favorite_topics"].append(topic)
            self._save()

    def remove_favorite_topic(self, topic: str) -> None:
        self._memory["favorite_topics"] = [
            t for t in self._memory["favorite_topics"] if t != topic
        ]
        self._save()

    def add_avoided_topic(self, topic: str) -> None:
        if topic not in self._memory["avoided_topics"]:
            self._memory["avoided_topics"].append(topic)
            self._save()

    # ── Statistics ──────────────────────────────────────────

    def record_published(self) -> None:
        """Record that a post was successfully published."""
        stats = self._memory["statistics"]
        stats["total_published"] = stats.get("total_published", 0) + 1
        stats["last_published_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def record_cancelled(self) -> None:
        """Record that a draft was cancelled."""
        stats = self._memory["statistics"]
        stats["total_cancelled"] = stats.get("total_cancelled", 0) + 1
        self._save()

    def get_statistics(self) -> Dict[str, Any]:
        return self._memory.get("statistics", {})

    def get_all_memory(self) -> Dict[str, Any]:
        """Return complete memory snapshot (for debugging/export)."""
        return dict(self._memory)

    def reset(self) -> None:
        """Reset all memory (use with caution)."""
        self._memory = self._default_memory()
        self._save()
        log.warning("Memory store reset to defaults")


# Module-level singleton
memory_store = MemoryStore()
