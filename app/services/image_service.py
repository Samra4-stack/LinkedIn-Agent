"""
app/services/image_service.py
──────────────────────────────
Multi-provider image service.
Tries providers in priority order: Unsplash → Pexels → Pixabay → DALL-E
Returns image URL, source, and alt text.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import List, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.prompts.image_prompt import build_dalle_prompt, build_search_keywords
from app.utils.logger import get_logger

log = get_logger(__name__)

TIMEOUT = httpx.Timeout(15.0)


@dataclass
class ImageResult:
    """Result from image fetching."""
    url: str
    source: str          # unsplash | pexels | pixabay | dalle | none
    alt_text: str
    photographer: Optional[str] = None
    photographer_url: Optional[str] = None
    download_url: Optional[str] = None  # For attribution tracking


class ImageServiceError(Exception):
    """Raised when all image providers fail."""
    pass


class ImageService:
    """
    Multi-provider image service with priority fallback.
    Provider priority is configurable via IMAGE_PROVIDER_PRIORITY env var.
    """

    def __init__(self) -> None:
        self.providers = settings.image_providers_list

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=False,
    )
    async def fetch_image(
        self,
        topic: str,
        post_hook: str = "",
        provider_override: Optional[str] = None,
    ) -> ImageResult:
        """
        Fetch a relevant image for the post topic.
        Tries providers in priority order.

        Args:
            topic: Post topic (used for search keywords)
            post_hook: Opening line (for DALL-E context)
            provider_override: Force a specific provider

        Returns:
            ImageResult with URL and metadata

        Raises:
            ImageServiceError: If all providers fail
        """
        providers = [provider_override] if provider_override else self.providers
        search_query = build_search_keywords(topic, post_hook)

        for provider in providers:
            try:
                log.info(f"Trying image provider: {provider} | query={search_query}")
                if provider == "unsplash":
                    result = await self._fetch_unsplash(search_query, topic)
                elif provider == "pexels":
                    result = await self._fetch_pexels(search_query, topic)
                elif provider == "pixabay":
                    result = await self._fetch_pixabay(search_query, topic)
                elif provider == "dalle":
                    result = await self._fetch_dalle(topic, post_hook)
                else:
                    log.warning(f"Unknown image provider: {provider}")
                    continue

                if result:
                    log.info(f"Image fetched | source={result.source} | url={result.url[:60]}...")
                    return result

            except Exception as e:
                log.warning(f"Image provider {provider} failed: {e}")
                continue

        log.error("All image providers failed")
        return ImageResult(
            url="",
            source="none",
            alt_text=f"Image for {topic}",
        )

    async def _fetch_unsplash(self, query: str, topic: str) -> Optional[ImageResult]:
        """Fetch image from Unsplash API."""
        if not settings.unsplash_api_key:
            return None

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": query,
                    "per_page": 20,
                    "page": random.randint(1, 3),
                    "orientation": "landscape",
                    "content_filter": "high",
                },
                headers={"Authorization": f"Client-ID {settings.unsplash_api_key}"},
            )
            response.raise_for_status()
            data = response.json()

            photos = data.get("results", [])
            if not photos:
                return None

            # Pick a random photo from the results so clicking "Change Image" actually changes it
            photo = random.choice(photos)
            
            # Add timestamp to bypass browser cache
            image_url = f"{photo['urls']['regular']}&t={int(time.time())}"
            
            return ImageResult(
                url=image_url,
                source="unsplash",
                alt_text=photo.get("alt_description") or f"{topic} - Photo by {photo['user']['name']}",
                photographer=photo["user"]["name"],
                photographer_url=photo["user"]["links"]["html"],
                download_url=photo["links"]["download"],
            )

    async def _fetch_pexels(self, query: str, topic: str) -> Optional[ImageResult]:
        """Fetch image from Pexels API."""
        if not settings.pexels_api_key:
            return None

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                "https://api.pexels.com/v1/search",
                params={
                    "query": query,
                    "per_page": 20,
                    "page": random.randint(1, 3),
                    "orientation": "landscape",
                },
                headers={"Authorization": settings.pexels_api_key},
            )
            response.raise_for_status()
            data = response.json()

            photos = data.get("photos", [])
            if not photos:
                return None

            photo = random.choice(photos)
            
            # Add timestamp to bypass browser cache
            image_url = f"{photo['src']['large2x']}?t={int(time.time())}"
            
            return ImageResult(
                url=image_url,
                source="pexels",
                alt_text=photo.get("alt") or f"{topic} - Photo by {photo['photographer']}",
                photographer=photo["photographer"],
                photographer_url=photo["photographer_url"],
            )

    async def _fetch_pixabay(self, query: str, topic: str) -> Optional[ImageResult]:
        """Fetch image from Pixabay API."""
        if not settings.pixabay_api_key:
            return None

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                "https://pixabay.com/api/",
                params={
                    "key": settings.pixabay_api_key,
                    "q": query,
                    "image_type": "photo",
                    "orientation": "horizontal",
                    "category": "science,technology,business",
                    "safesearch": "true",
                    "per_page": 20,
                    "page": random.randint(1, 3),
                },
            )
            response.raise_for_status()
            data = response.json()

            hits = data.get("hits", [])
            if not hits:
                return None

            photo = random.choice(hits)
            
            # Add timestamp to bypass browser cache
            image_url = f"{photo['largeImageURL']}?t={int(time.time())}"
            
            return ImageResult(
                url=image_url,
                source="pixabay",
                alt_text=f"{topic} - via Pixabay",
                photographer=photo.get("user"),
            )

    async def _fetch_dalle(self, topic: str, post_hook: str) -> Optional[ImageResult]:
        """Generate image using DALL-E 3."""
        if not settings.openai_api_key:
            return None

        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)

            import asyncio
            loop = asyncio.get_event_loop()
            prompt = build_dalle_prompt(topic, post_hook)

            def _sync_call():
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size=settings.dalle_image_size,
                    quality=settings.dalle_image_quality,
                    style=settings.dalle_image_style,
                    n=1,
                )
                return response.data[0].url

            url = await loop.run_in_executor(None, _sync_call)
            return ImageResult(
                url=url,
                source="dalle",
                alt_text=f"AI-generated image for {topic}",
            )

        except Exception as e:
            log.error(f"DALL-E image generation failed: {e}")
            return None


# Module-level singleton
image_service = ImageService()
