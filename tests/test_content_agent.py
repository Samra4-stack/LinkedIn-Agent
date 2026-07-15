"""
tests/test_content_agent.py
────────────────────────────
Unit tests for the ContentAgent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.content_agent import ContentAgent
from app.services.ai_service import GeneratedPost
from app.services.image_service import ImageResult


MOCK_GENERATED_POST = GeneratedPost({
    "hook": "🚀 Python is the most popular language in 2024.",
    "body": "Here's why Python dominates:\n\n1. Simplicity\n2. Rich ecosystem\n3. AI/ML support",
    "cta": "What's your favorite Python library? Comment below!",
    "full_post": "🚀 Python is the most popular language in 2024.\n\nHere's why Python dominates:\n\n1. Simplicity\n2. Rich ecosystem\n3. AI/ML support\n\nWhat's your favorite Python library? Comment below!",
    "hashtags": ["python", "programming", "coding"],
    "topic_angle": "Python's dominance in 2024",
})

MOCK_IMAGE_RESULT = ImageResult(
    url="https://images.unsplash.com/photo-123",
    source="unsplash",
    alt_text="Python programming",
    photographer="Test Photographer",
)


class TestContentAgent:
    """Tests for ContentAgent."""

    @pytest.mark.asyncio
    async def test_generate_post_with_topic(self, db):
        """Test post generation with explicit topic."""
        agent = ContentAgent(db=db)

        with patch("app.agents.content_agent.AIService") as MockAI, \
             patch("app.agents.content_agent.image_service") as mock_img, \
             patch("app.agents.content_agent.link_service") as mock_links, \
             patch("app.agents.content_agent.memory_store") as mock_memory, \
             patch("app.agents.content_agent.settings") as mock_settings:

            # Setup mocks
            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_post = AsyncMock(return_value=MOCK_GENERATED_POST)
            MockAI.return_value = mock_ai_instance

            mock_img.fetch_image = AsyncMock(return_value=MOCK_IMAGE_RESULT)
            mock_links.find_links = AsyncMock(return_value=[{"url": "https://python.org", "title": "Python"}])
            mock_links.get_urls_only = MagicMock(return_value=["https://python.org"])

            mock_memory.select_next_topic = MagicMock(return_value="Python")
            mock_memory.get_recent_topics = MagicMock(return_value=[])
            mock_memory.get_recent_angles = MagicMock(return_value=[])
            mock_memory.get_preferred_hashtags = MagicMock(return_value=[])
            mock_memory.get_writing_style = MagicMock(return_value="professional")
            mock_memory.is_duplicate_content = MagicMock(return_value=False)
            mock_memory.record_topic_used = MagicMock()
            mock_memory.record_content_hash = MagicMock()

            mock_settings.topics_list = ["Python", "AI"]
            mock_settings.max_hashtags = 10
            mock_settings.post_language = "English"
            mock_settings.ai_provider = "openai"
            mock_settings.openai_model = "gpt-4o"
            mock_settings.gemini_model = "gemini-1.5-pro"

            draft = await agent.generate_post(topic="Python")

        assert draft is not None
        assert draft.topic == "Python"
        assert draft.content == MOCK_GENERATED_POST.full_post
        assert draft.image_url == MOCK_IMAGE_RESULT.url
        assert draft.image_source == "unsplash"

    @pytest.mark.asyncio
    async def test_generate_post_auto_selects_topic(self, db):
        """Test that topic is auto-selected when not provided."""
        agent = ContentAgent(db=db)

        with patch("app.agents.content_agent.AIService") as MockAI, \
             patch("app.agents.content_agent.image_service") as mock_img, \
             patch("app.agents.content_agent.link_service") as mock_links, \
             patch("app.agents.content_agent.memory_store") as mock_memory, \
             patch("app.agents.content_agent.crud") as mock_crud, \
             patch("app.agents.content_agent.settings") as mock_settings:

            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_post = AsyncMock(return_value=MOCK_GENERATED_POST)
            MockAI.return_value = mock_ai_instance

            mock_img.fetch_image = AsyncMock(return_value=MOCK_IMAGE_RESULT)
            mock_links.find_links = AsyncMock(return_value=[])
            mock_links.get_urls_only = MagicMock(return_value=[])

            mock_memory.select_next_topic = MagicMock(return_value="AI")
            mock_memory.get_recent_topics = MagicMock(return_value=[])
            mock_memory.get_recent_angles = MagicMock(return_value=[])
            mock_memory.get_preferred_hashtags = MagicMock(return_value=[])
            mock_memory.get_writing_style = MagicMock(return_value="professional")
            mock_memory.is_duplicate_content = MagicMock(return_value=False)
            mock_memory.record_topic_used = MagicMock()
            mock_memory.record_content_hash = MagicMock()

            mock_crud.get_settings = MagicMock(return_value=None)
            mock_crud.create_draft = MagicMock(return_value=MagicMock(
                id=1, topic="AI", content=MOCK_GENERATED_POST.full_post,
                hook=MOCK_GENERATED_POST.hook, body=MOCK_GENERATED_POST.body,
                cta=MOCK_GENERATED_POST.cta, hashtags=["#ai"], links=[],
                image_url=MOCK_IMAGE_RESULT.url, image_source="unsplash",
                image_alt_text="AI image", status="pending_review",
                ai_provider="openai", ai_model="gpt-4o", user_id=None,
            ))

            mock_settings.topics_list = ["AI", "Python"]
            mock_settings.max_hashtags = 10
            mock_settings.post_language = "English"
            mock_settings.ai_provider = "openai"
            mock_settings.openai_model = "gpt-4o"
            mock_settings.gemini_model = "gemini-1.5-pro"

            draft = await agent.generate_post()  # No topic provided

        # Should have auto-selected "AI"
        mock_memory.select_next_topic.assert_called_once()

    @pytest.mark.asyncio
    async def test_regenerate_hashtags(self, db, sample_draft):
        """Test hashtag regeneration."""
        agent = ContentAgent(db=db)

        with patch("app.agents.content_agent.AIService") as MockAI, \
             patch("app.agents.content_agent.memory_store") as mock_memory, \
             patch("app.agents.content_agent.settings") as mock_settings:

            mock_ai_instance = MagicMock()
            mock_ai_instance.generate_hashtags = AsyncMock(
                return_value=["newhashtag1", "newhashtag2", "newhashtag3"]
            )
            MockAI.return_value = mock_ai_instance

            mock_memory.get_preferred_hashtags = MagicMock(return_value=[])
            mock_settings.max_hashtags = 10

            updated_draft = await agent.regenerate_parts(
                draft=sample_draft,
                parts=["hashtags"],
            )

        assert updated_draft is not None

    @pytest.mark.asyncio
    async def test_regenerate_image(self, db, sample_draft):
        """Test image regeneration."""
        agent = ContentAgent(db=db)

        with patch("app.agents.content_agent.image_service") as mock_img:
            new_image = ImageResult(
                url="https://new-image-url.com/photo.jpg",
                source="pexels",
                alt_text="New image",
            )
            mock_img.fetch_image = AsyncMock(return_value=new_image)

            updated_draft = await agent.regenerate_parts(
                draft=sample_draft,
                parts=["image"],
            )

        assert updated_draft.image_url == "https://new-image-url.com/photo.jpg"
        assert updated_draft.image_source == "pexels"
