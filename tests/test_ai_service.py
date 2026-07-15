"""
tests/test_ai_service.py
─────────────────────────
Unit tests for the AI service (OpenAI/Gemini generation).
Uses respx to mock HTTP calls — no real API calls made.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_service import AIService, AIServiceError, GeneratedPost


# ─── Fixtures ────────────────────────────────────────────────

MOCK_POST_RESPONSE = {
    "hook": "🤖 AI is transforming the way we work.",
    "body": "Here are 5 ways artificial intelligence is reshaping careers:\n\n1. Automation of repetitive tasks\n2. Enhanced decision-making\n3. Personalized learning paths\n4. Faster data analysis\n5. New job categories emerging",
    "cta": "Which AI tool has changed your workflow the most? Share in the comments 👇",
    "full_post": "🤖 AI is transforming the way we work.\n\nHere are 5 ways artificial intelligence is reshaping careers...\n\nWhich AI tool has changed your workflow the most? Share in the comments 👇",
    "hashtags": ["artificialintelligence", "ai", "machinelearning", "python", "tech"],
    "topic_angle": "Career impact of AI on modern professionals",
}


# ─── Tests ───────────────────────────────────────────────────

class TestGeneratedPost:
    """Tests for GeneratedPost data class."""

    def test_init_from_dict(self):
        post = GeneratedPost(MOCK_POST_RESPONSE)
        assert post.hook == MOCK_POST_RESPONSE["hook"]
        assert post.body == MOCK_POST_RESPONSE["body"]
        assert post.cta == MOCK_POST_RESPONSE["cta"]
        assert post.full_post == MOCK_POST_RESPONSE["full_post"]
        assert post.hashtags == MOCK_POST_RESPONSE["hashtags"]
        assert post.topic_angle == MOCK_POST_RESPONSE["topic_angle"]

    def test_to_dict(self):
        post = GeneratedPost(MOCK_POST_RESPONSE)
        result = post.to_dict()
        assert isinstance(result, dict)
        assert "hook" in result
        assert "full_post" in result
        assert "hashtags" in result

    def test_empty_data(self):
        post = GeneratedPost({})
        assert post.hook == ""
        assert post.hashtags == []


class TestAIService:
    """Tests for AIService."""

    def test_init_default_provider(self):
        with patch("app.services.ai_service.settings") as mock_settings:
            mock_settings.ai_provider = "openai"
            service = AIService()
            assert service.provider == "openai"

    def test_init_custom_provider(self):
        service = AIService(provider="gemini")
        assert service.provider == "gemini"

    def test_parse_json_response_valid(self):
        service = AIService()
        result = service._parse_json_response(json.dumps(MOCK_POST_RESPONSE))
        assert result["hook"] == MOCK_POST_RESPONSE["hook"]

    def test_parse_json_response_with_markdown(self):
        """Should strip markdown code fences."""
        service = AIService()
        wrapped = f"```json\n{json.dumps(MOCK_POST_RESPONSE)}\n```"
        result = service._parse_json_response(wrapped)
        assert result["hook"] == MOCK_POST_RESPONSE["hook"]

    def test_parse_json_response_empty_raises(self):
        service = AIService()
        with pytest.raises(AIServiceError):
            service._parse_json_response("")

    def test_parse_json_response_invalid_raises(self):
        service = AIService()
        with pytest.raises(AIServiceError):
            service._parse_json_response("this is not json at all {{{{")

    @pytest.mark.asyncio
    async def test_generate_post_openai_success(self):
        """Test successful OpenAI post generation with mocked client."""
        service = AIService(provider="openai")

        with patch.object(service, "_generate_openai", new_callable=AsyncMock) as mock_openai:
            mock_openai.return_value = json.dumps(MOCK_POST_RESPONSE)

            with patch("app.services.ai_service.settings") as mock_settings:
                mock_settings.ai_provider = "openai"
                mock_settings.openai_api_key = "test-key"
                mock_settings.openai_model = "gpt-4o"
                mock_settings.openai_max_tokens = 1500
                mock_settings.openai_temperature = 0.8
                mock_settings.post_language = "English"

                result = await service.generate_post(topic="Artificial Intelligence")

        assert isinstance(result, GeneratedPost)
        assert result.hook == MOCK_POST_RESPONSE["hook"]
        assert len(result.hashtags) > 0

    @pytest.mark.asyncio
    async def test_generate_hashtags_success(self):
        """Test hashtag generation."""
        service = AIService(provider="openai")

        with patch.object(service, "_call_provider", new_callable=AsyncMock) as mock:
            mock.return_value = '["artificialintelligence", "ai", "machinelearning"]'
            result = await service.generate_hashtags(
                topic="AI",
                post_content="Sample post content",
                count=3,
            )

        assert isinstance(result, list)
        assert len(result) == 3
        assert "artificialintelligence" in result

    @pytest.mark.asyncio
    async def test_generate_hashtags_fallback_on_error(self):
        """Should return fallback hashtags on parse error."""
        service = AIService(provider="openai")

        with patch.object(service, "_call_provider", new_callable=AsyncMock) as mock:
            mock.return_value = "INVALID JSON"

            result = await service.generate_hashtags(
                topic="Python",
                post_content="Sample content",
                count=5,
            )

        # Should return fallback hashtags
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_post_no_api_key_raises(self):
        """Should raise when API key is missing."""
        service = AIService(provider="openai")

        with patch("app.services.ai_service.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            mock_settings.gemini_api_key = ""

            with pytest.raises(AIServiceError):
                await service._generate_openai("test prompt")
