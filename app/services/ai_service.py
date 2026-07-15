"""
app/services/ai_service.py
──────────────────────────
AI content generation service.
Supports Groq (Llama), Google Gemini, and OpenAI with automatic fallback.

Provider priority (default): groq → gemini → openai

IMPORTANT — Groq / Llama notes:
  - Uses OpenAI-compatible API at https://api.groq.com/openai/v1
  - Does NOT support response_format={"type": "json_object"} on all models
  - We use prompt-level JSON instruction instead of API-level JSON mode
  - Key starts with "gsk_" — stored under OPENAI_API_KEY or GROQ_API_KEY
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.prompts.hashtag_prompt import build_hashtag_prompt
from app.prompts.post_prompt import SYSTEM_PROMPT, build_post_prompt
from app.utils.logger import get_logger

log = get_logger(__name__)


class AIServiceError(Exception):
    """Raised when AI generation fails."""
    pass


class GeneratedPost:
    """Structured result from AI post generation."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self.hook: str = data.get("hook", "")
        self.body: str = data.get("body", "")
        self.cta: str = data.get("cta", "")
        self.full_post: str = data.get("full_post", "")
        self.hashtags: List[str] = data.get("hashtags", [])
        self.topic_angle: str = data.get("topic_angle", "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook": self.hook,
            "body": self.body,
            "cta": self.cta,
            "full_post": self.full_post,
            "hashtags": self.hashtags,
            "topic_angle": self.topic_angle,
        }


class AIService:
    """
    Multi-provider AI service for LinkedIn post generation.

    Supported providers:
      - groq    : Llama 3.3 70B via api.groq.com (free, fast)
      - gemini  : Google Gemini via google.generativeai
      - openai  : OpenAI GPT-4o

    Fallback chain: groq → gemini → openai (first available wins)
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = provider or settings.ai_provider
        self._groq_client = None
        self._openai_client = None
        self._gemini_client = None

    # ── Client Factories ────────────────────────────────────────

    def _get_groq_client(self):
        """Lazy-initialize Groq client (OpenAI SDK with custom base_url)."""
        if self._groq_client is None:
            try:
                from openai import OpenAI
                api_key = settings.effective_groq_key
                if not api_key:
                    raise AIServiceError(
                        "Groq API key not found. Set GROQ_API_KEY or OPENAI_API_KEY (gsk_...) in .env"
                    )
                self._groq_client = OpenAI(
                    api_key=api_key,
                    base_url=settings.groq_base_url,
                )
                log.info(f"Groq client initialized | model={settings.effective_groq_model}")
            except ImportError:
                raise AIServiceError("openai package not installed. Run: pip install openai")
        return self._groq_client

    def _get_openai_client(self):
        """Lazy-initialize standard OpenAI client."""
        if self._openai_client is None:
            try:
                from openai import OpenAI
                if not settings.openai_api_key or settings.openai_api_key.startswith("gsk_"):
                    raise AIServiceError("OPENAI_API_KEY is not configured (or is a Groq key)")
                self._openai_client = OpenAI(api_key=settings.openai_api_key)
            except ImportError:
                raise AIServiceError("openai package not installed. Run: pip install openai")
        return self._openai_client

    def _get_gemini_client(self):
        """Lazy-initialize Google Gemini client."""
        if self._gemini_client is None:
            try:
                import google.generativeai as genai
                if not settings.gemini_api_key:
                    raise AIServiceError("GEMINI_API_KEY is not configured")
                genai.configure(api_key=settings.gemini_api_key)
                self._gemini_client = genai.GenerativeModel(settings.gemini_model)
                log.info(f"Gemini client initialized | model={settings.gemini_model}")
            except ImportError:
                raise AIServiceError(
                    "google-generativeai package not installed. Run: pip install google-generativeai"
                )
        return self._gemini_client

    # ── Main Generation ─────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError,)),
        reraise=True,
    )
    async def generate_post(
        self,
        topic: str,
        style: str = "professional",
        custom_instructions: Optional[str] = None,
        recent_topics: Optional[List[str]] = None,
        preferred_hashtags: Optional[List[str]] = None,
        language: str = "English",
    ) -> GeneratedPost:
        """
        Generate a LinkedIn post using the configured AI provider.

        Args:
            topic: Topic for the post
            style: Writing style (professional | casual | storytelling | educational)
            custom_instructions: Additional instructions
            recent_topics: Recently covered topics/angles to avoid
            preferred_hashtags: User's hashtag preferences
            language: Output language

        Returns:
            GeneratedPost object with all post fields

        Raises:
            AIServiceError: If generation fails after all retries
        """
        prompt = build_post_prompt(
            topic=topic,
            style=style,
            custom_instructions=custom_instructions,
            recent_topics=recent_topics,
            preferred_hashtags=preferred_hashtags,
            language=language,
        )

        log.info(f"Generating post | provider={self.provider} | topic={topic} | style={style}")

        # Build fallback chain based on available keys
        providers_to_try = self._build_provider_chain()

        last_error: Optional[Exception] = None
        for provider in providers_to_try:
            try:
                log.info(f"Trying provider: {provider}")
                result = await self._call_provider(provider, prompt)
                parsed = self._parse_json_response(result)
                post = GeneratedPost(parsed)

                # Validate the response has required fields
                if not post.full_post:
                    raise AIServiceError(f"Provider {provider} returned empty full_post")

                log.info(
                    f"Post generated | provider={provider} | topic={topic} | "
                    f"chars={len(post.full_post)}"
                )
                return post

            except AIServiceError as e:
                last_error = e
                log.warning(f"Provider {provider} failed: {e}. Trying next...")
                continue
            except Exception as e:
                last_error = e
                log.warning(f"Provider {provider} error: {e}. Trying next...")
                continue

        raise AIServiceError(
            f"All AI providers failed. Last error: {last_error}. "
            f"Check your API keys in .env"
        )

    def _build_provider_chain(self) -> List[str]:
        """
        Build ordered list of providers to try.
        Starts with configured provider, then falls back to available ones.
        """
        chain = [self.provider]
        # Add fallbacks if not already in chain
        fallbacks = ["groq", "gemini", "openai"]
        for fb in fallbacks:
            if fb not in chain:
                chain.append(fb)
        return chain

    async def _call_provider(self, provider: str, prompt: str) -> str:
        """Dispatch to the correct provider."""
        if provider == "groq":
            return await self._generate_groq(prompt)
        elif provider == "gemini":
            return await self._generate_gemini(prompt)
        elif provider == "openai":
            return await self._generate_openai(prompt)
        else:
            raise AIServiceError(f"Unknown provider: {provider}")

    # ── Provider Implementations ────────────────────────────────

    async def _generate_groq(self, prompt: str) -> str:
        """
        Call Groq API using OpenAI-compatible SDK.

        IMPORTANT: Groq's Llama models do NOT support response_format=json_object.
        We rely on prompt-level JSON instructions instead.
        """
        api_key = settings.effective_groq_key
        if not api_key:
            raise AIServiceError(
                "Groq API key not configured. "
                "Set GROQ_API_KEY=gsk_... in your .env file."
            )

        client = self._get_groq_client()
        model = settings.effective_groq_model

        import asyncio
        loop = asyncio.get_event_loop()

        def _sync_call():
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature,
                # NOTE: No response_format here — Groq/Llama doesn't support JSON mode
                # on all models. The prompt instructs JSON output instead.
            )
            return response.choices[0].message.content

        result = await loop.run_in_executor(None, _sync_call)
        log.debug(f"Groq response received | model={model}")
        return result

    async def _generate_openai(self, prompt: str) -> str:
        """Call standard OpenAI API (GPT-4o etc.)."""
        if not settings.openai_api_key or settings.openai_api_key.startswith("gsk_"):
            raise AIServiceError(
                "OpenAI API key not configured. "
                "Set OPENAI_API_KEY=sk-... in your .env (not a Groq key)."
            )

        client = self._get_openai_client()

        import asyncio
        loop = asyncio.get_event_loop()

        def _sync_call():
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content

        result = await loop.run_in_executor(None, _sync_call)
        log.debug(f"OpenAI response received | model={settings.openai_model}")
        return result

    async def _generate_gemini(self, prompt: str) -> str:
        """Call Google Gemini API."""
        if not settings.gemini_api_key:
            raise AIServiceError("GEMINI_API_KEY is not configured in .env")

        model = self._get_gemini_client()

        import asyncio
        loop = asyncio.get_event_loop()

        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

        def _sync_call():
            response = model.generate_content(full_prompt)
            return response.text

        result = await loop.run_in_executor(None, _sync_call)
        log.debug(f"Gemini response received | model={settings.gemini_model}")
        return result

    # ── Hashtag Generation ──────────────────────────────────────

    async def generate_hashtags(
        self,
        topic: str,
        post_content: str,
        preferred_hashtags: Optional[List[str]] = None,
        count: int = 10,
    ) -> List[str]:
        """
        Generate hashtags for a post.

        Args:
            topic: Post topic
            post_content: Full post content
            preferred_hashtags: Preferred hashtag categories
            count: Number of hashtags to generate

        Returns:
            List of hashtag strings (without #)
        """
        prompt = build_hashtag_prompt(topic, post_content, preferred_hashtags, count)
        log.info(f"Generating hashtags | topic={topic} | count={count}")

        try:
            result = await self._call_provider(self.provider, prompt)

            # Parse JSON array — handle extra text around it
            cleaned = result.strip()
            if not cleaned.startswith("["):
                match = re.search(r"\[.*?\]", cleaned, re.DOTALL)
                if match:
                    cleaned = match.group(0)

            hashtags = json.loads(cleaned)
            return [str(h).strip().lower().replace("#", "") for h in hashtags][:count]

        except Exception as e:
            log.warning(f"Hashtag generation failed ({e}), using curated fallbacks")
            from app.prompts.hashtag_prompt import HASHTAG_CATEGORIES
            fallback = HASHTAG_CATEGORIES.get(topic, ["linkedin", "tech", "professional"])
            return fallback[:count]

    # ── Response Parsing ────────────────────────────────────────

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from AI response robustly.
        Handles markdown fences, extra text around JSON, and common formatting issues.

        Args:
            response: Raw AI response string

        Returns:
            Parsed dictionary

        Raises:
            AIServiceError: If JSON cannot be extracted
        """
        if not response:
            raise AIServiceError("Empty response from AI provider")

        cleaned = response.strip()

        # Step 1: Remove markdown code fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()

        # Step 2: Try direct parse
        try:
            return json.loads(cleaned, strict=False)
        except json.JSONDecodeError:
            pass

        # Step 3: Extract first {...} block (handles text before/after JSON)
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0), strict=False)
            except json.JSONDecodeError:
                pass

        # Step 4: Try to fix common issues (trailing commas, single quotes)
        fixed = re.sub(r",\s*([}\]])", r"\1", cleaned)  # trailing commas
        try:
            return json.loads(fixed, strict=False)
        except json.JSONDecodeError:
            pass

        raise AIServiceError(
            f"Could not parse JSON from AI response. "
            f"First 300 chars: {cleaned[:300]}"
        )


# Module-level singleton
ai_service = AIService()
