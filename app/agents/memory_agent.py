"""
app/agents/memory_agent.py
───────────────────────────
High-level memory management agent.
Provides a clean interface for reading/writing agent memory,
combining MemoryStore (JSON) and database queries.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import crud
from app.memory.memory_store import memory_store
from app.utils.logger import get_logger

log = get_logger(__name__)


class MemoryAgent:
    """
    Manages agent memory across sessions.
    Coordinates between JSON memory store and SQLite database.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_context_for_generation(self) -> Dict[str, Any]:
        """
        Compile all memory context needed for post generation.

        Returns:
            Dict with recent_topics, avoided_angles, preferred_hashtags, etc.
        """
        # Merge memory + DB for comprehensive deduplication
        memory_recent = set(memory_store.get_recent_topics(days=30))
        db_recent = set(crud.get_recent_topics(self.db, days=30))
        combined_recent = list(memory_recent | db_recent)

        return {
            "recent_topics": combined_recent,
            "preferred_hashtags": memory_store.get_preferred_hashtags(),
            "writing_style": memory_store.get_writing_style(),
            "favorite_topics": memory_store.get_all_memory().get("favorite_topics", []),
            "avoided_topics": memory_store.get_all_memory().get("avoided_topics", []),
            "statistics": memory_store.get_statistics(),
        }

    def select_topic(self, available_topics: Optional[List[str]] = None) -> str:
        """
        Select the next topic using memory-aware algorithm.

        Args:
            available_topics: Topics to choose from. Uses settings default if None.

        Returns:
            Selected topic string
        """
        if not available_topics:
            from app.config import settings
            available_topics = settings.topics_list

        return memory_store.select_next_topic(available_topics)

    def update_preferences(
        self,
        hashtags: Optional[List[str]] = None,
        style: Optional[str] = None,
        favorite_topics: Optional[List[str]] = None,
        avoid_topics: Optional[List[str]] = None,
    ) -> None:
        """
        Update user preferences in memory.

        Args:
            hashtags: Preferred hashtags list
            style: Writing style preference
            favorite_topics: Topics to prioritize
            avoid_topics: Topics to skip
        """
        if hashtags is not None:
            memory_store.update_preferred_hashtags(hashtags)
            log.info(f"Updated preferred hashtags: {hashtags[:5]}")

        if style is not None:
            memory_store.update_writing_style(style)
            log.info(f"Updated writing style: {style}")

        if favorite_topics is not None:
            for topic in favorite_topics:
                memory_store.add_favorite_topic(topic)
            log.info(f"Updated favorite topics: {favorite_topics}")

        if avoid_topics is not None:
            for topic in avoid_topics:
                memory_store.add_avoided_topic(topic)
            log.info(f"Added avoided topics: {avoid_topics}")

    def get_full_memory_snapshot(self) -> Dict[str, Any]:
        """Return complete memory for debugging or export."""
        db_stats = crud.get_analytics_summary(self.db)
        memory_data = memory_store.get_all_memory()
        return {
            "memory": memory_data,
            "db_stats": db_stats,
        }

    def check_topic_freshness(self, topic: str) -> Dict[str, Any]:
        """
        Check whether a topic is safe to use.

        Args:
            topic: Topic to check

        Returns:
            Dict with freshness info
        """
        is_overused = memory_store.is_topic_overused(topic, min_gap_days=7)
        recent_angles = memory_store.get_recent_angles(topic, days=90)
        db_overused = crud.is_topic_recently_used(self.db, topic, days=7)

        return {
            "topic": topic,
            "is_safe_to_use": not (is_overused or db_overused),
            "was_used_recently": is_overused or db_overused,
            "recent_angles_covered": recent_angles,
            "recommendation": "safe" if not (is_overused or db_overused) else "wait or use different angle",
        }
