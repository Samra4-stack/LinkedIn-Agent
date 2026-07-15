"""
app/agents/content_agent.py
────────────────────────────
Core AI orchestration agent.
Coordinates AI service, image service, link service, and memory
to produce a complete LinkedIn post draft.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import crud
from app.database.models import Draft
from app.memory.memory_store import memory_store
from app.services.ai_service import AIService, AIServiceError
from app.services.image_service import image_service
from app.services.link_service import link_service
from app.utils.helpers import clean_hashtags, compute_hash
from app.utils.logger import get_logger

log = get_logger(__name__)


class ContentAgent:
    """
    Orchestrates the full LinkedIn post generation pipeline:

    1. Select topic (memory-aware, no duplicates)
    2. Generate post content via AI
    3. Fetch relevant image
    4. Find relevant links
    5. Assemble and persist draft
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    async def generate_post(
        self,
        topic: Optional[str] = None,
        ai_provider: Optional[str] = None,
        image_provider: Optional[str] = None,
        style: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Draft:
        """
        Generate a complete LinkedIn post draft.

        Args:
            topic: Specific topic, or None to auto-select
            ai_provider: Override AI provider
            image_provider: Override image provider
            style: Writing style
            custom_instructions: Extra instructions for AI
            user_id: User ID for user-specific settings

        Returns:
            Draft ORM object saved to database
        """
        # ── Step 1: Select topic ─────────────────────────────
        if not topic:
            user_settings = crud.get_settings(self.db, user_id)
            available_topics = (
                user_settings.topics
                if user_settings and user_settings.topics
                else settings.topics_list
            )
            topic = memory_store.select_next_topic(available_topics)
            log.info(f"Auto-selected topic: {topic}")

        # ── Step 2: Gather context from memory ───────────────
        recent_topics = memory_store.get_recent_topics(days=30)
        recent_angles = memory_store.get_recent_angles(topic, days=90)
        preferred_hashtags = memory_store.get_preferred_hashtags()
        writing_style = style or memory_store.get_writing_style()
        language = settings.post_language

        # Combine recent topics and angles to avoid for prompt
        avoid_context = []
        if recent_angles:
            avoid_context.extend(f"{topic} - {angle}" for angle in recent_angles[:5])
        if recent_topics and topic not in [t.split(" - ")[0] for t in avoid_context]:
            avoid_context.extend(recent_topics[:5])

        log.info(f"Starting content generation | topic={topic} | style={writing_style}")

        # ── Step 3: Generate post content ────────────────────
        ai = AIService(provider=ai_provider)
        try:
            generated = await ai.generate_post(
                topic=topic,
                style=writing_style,
                custom_instructions=custom_instructions,
                recent_topics=avoid_context[:10],
                preferred_hashtags=preferred_hashtags,
                language=language,
            )
        except AIServiceError as e:
            log.error(f"AI generation failed: {e}")
            raise

        # ── Step 4: Duplicate check ──────────────────────────
        content_hash = compute_hash(generated.full_post)
        if memory_store.is_duplicate_content(content_hash):
            log.warning("Duplicate content detected, regenerating...")
            # Retry once with extra instruction to be different
            generated = await ai.generate_post(
                topic=topic,
                style=writing_style,
                custom_instructions="Make this completely different from any previous posts. Use a unique angle.",
                recent_topics=avoid_context[:10],
                preferred_hashtags=preferred_hashtags,
                language=language,
            )
            content_hash = compute_hash(generated.full_post)

        # ── Step 5: Clean hashtags ───────────────────────────
        hashtags = clean_hashtags([f"#{h}" for h in generated.hashtags])
        hashtags = hashtags[: settings.max_hashtags]

        # ── Step 6: Fetch image ──────────────────────────────
        log.info("Fetching image...")
        image_result = await image_service.fetch_image(
            topic=topic,
            post_hook=generated.hook,
            provider_override=image_provider,
        )

        # ── Step 7: Find relevant links ──────────────────────
        log.info("Searching for links...")
        links_data = await link_service.find_links(
            topic=topic,
            post_content=generated.full_post,
            count=3,
        )
        link_urls = link_service.get_urls_only(links_data)

        # ── Step 8: Determine AI model used ──────────────────
        provider_used = ai_provider or settings.ai_provider
        model_used = settings.openai_model if provider_used == "openai" else settings.gemini_model

        # ── Step 9: Save draft to database ───────────────────
        draft = crud.create_draft(
            self.db,
            topic=topic,
            hook=generated.hook,
            body=generated.body,
            cta=generated.cta,
            content=generated.full_post,
            hashtags=hashtags,
            links=link_urls,
            image_url=image_result.url,
            image_source=image_result.source,
            image_alt_text=image_result.alt_text,
            ai_provider=provider_used,
            ai_model=model_used,
            content_hash=content_hash,
            user_id=user_id,
        )

        # ── Step 10: Update memory ───────────────────────────
        memory_store.record_topic_used(topic, angle=generated.topic_angle)
        memory_store.record_content_hash(content_hash)

        log.info(
            f"Draft created | id={draft.id} | topic={topic} | "
            f"chars={len(generated.full_post)} | image={image_result.source}"
        )
        return draft

    async def regenerate_parts(
        self,
        draft: Draft,
        parts: List[str],
        topic_override: Optional[str] = None,
    ) -> Draft:
        """
        Regenerate specific parts of an existing draft.

        Args:
            draft: Existing draft to update
            parts: List of parts to regenerate: post | hashtags | image | links | hook | cta
            topic_override: New topic (for full post regeneration)

        Returns:
            Updated Draft object
        """
        updates: Dict[str, Any] = {}
        topic = topic_override or draft.topic

        if "post" in parts:
            # Full post regeneration
            log.info(f"Regenerating full post | draft_id={draft.id} | topic={topic}")
            ai = AIService()
            recent_topics = memory_store.get_recent_topics(days=30)
            generated = await ai.generate_post(
                topic=topic,
                style=memory_store.get_writing_style(),
                recent_topics=recent_topics[:10],
            )
            updates.update({
                "topic": topic,
                "hook": generated.hook,
                "body": generated.body,
                "cta": generated.cta,
                "content": generated.full_post,
            })
            memory_store.record_topic_used(topic, angle=generated.topic_angle)

        if "hook" in parts and "post" not in parts:
            # Regenerate just the hook
            ai = AIService()
            generated = await ai.generate_post(topic=topic, style="professional")
            updates["hook"] = generated.hook

        if "cta" in parts and "post" not in parts:
            ai = AIService()
            generated = await ai.generate_post(topic=topic, style="professional")
            updates["cta"] = generated.cta

        if "hashtags" in parts:
            log.info(f"Regenerating hashtags | draft_id={draft.id}")
            ai = AIService()
            new_hashtags = await ai.generate_hashtags(
                topic=topic,
                post_content=draft.content,
                preferred_hashtags=memory_store.get_preferred_hashtags(),
                count=settings.max_hashtags,
            )
            updates["hashtags"] = clean_hashtags([f"#{h}" for h in new_hashtags])

        if "image" in parts:
            log.info(f"Regenerating image | draft_id={draft.id}")
            image_result = await image_service.fetch_image(
                topic=topic,
                post_hook=draft.hook or "",
            )
            updates["image_url"] = image_result.url
            updates["image_source"] = image_result.source
            updates["image_alt_text"] = image_result.alt_text

        if "links" in parts:
            log.info(f"Regenerating links | draft_id={draft.id}")
            links_data = await link_service.find_links(
                topic=topic,
                post_content=draft.content,
                count=3,
            )
            updates["links"] = link_service.get_urls_only(links_data)

        if updates:
            draft = crud.update_draft(self.db, draft, **updates)

        return draft
