"""
app/agents/review_agent.py
───────────────────────────
Human-in-the-loop review workflow manager.
Enforces the review state machine before any post is published.

States:
    DRAFT → PENDING_REVIEW → APPROVED → PUBLISHED
                          ↘ CANCELLED
                          ↘ EDITING → PENDING_REVIEW
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.database import crud
from app.database.models import Draft, PostStatus
from app.models.schemas import PreviewResponse
from app.utils.helpers import build_post_preview, now_utc
from app.utils.logger import get_logger

log = get_logger(__name__)


class ReviewError(Exception):
    """Raised when a review workflow rule is violated."""
    pass


class ReviewAgent:
    """
    Manages the human-in-the-loop review workflow.
    Ensures no post is published without explicit human approval.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_preview(self, draft_id: int) -> PreviewResponse:
        """
        Build a rich preview of a draft for human review.

        Args:
            draft_id: ID of the draft to preview

        Returns:
            PreviewResponse with all post data and review options

        Raises:
            ReviewError: If draft not found
        """
        draft = crud.get_draft(self.db, draft_id)
        if not draft:
            raise ReviewError(f"Draft {draft_id} not found")

        content = draft.content or ""
        word_count = len(content.split())
        read_time = max(1, word_count // 200 * 60)  # ~200 WPM reading speed

        preview = PreviewResponse(
            draft_id=draft.id,
            topic=draft.topic,
            hook=draft.hook,
            body=draft.body,
            cta=draft.cta,
            full_content=content,
            hashtags=draft.hashtags or [],
            links=draft.links or [],
            image_url=draft.image_url,
            image_source=draft.image_source,
            image_alt_text=draft.image_alt_text,
            scheduled_time=draft.scheduled_time,
            status=draft.status,
            edit_count=draft.edit_count or 0,
            character_count=len(content),
            estimated_read_time_seconds=read_time,
        )
        log.info(f"Preview generated | draft_id={draft_id} | chars={len(content)}")
        return preview

    def get_text_preview(self, draft_id: int) -> str:
        """Return a formatted text preview (for CLI/logging)."""
        draft = crud.get_draft(self.db, draft_id)
        if not draft:
            raise ReviewError(f"Draft {draft_id} not found")

        from pytz import timezone as pytz_tz
        from app.config import settings as app_settings

        scheduled = "Not scheduled"
        if draft.scheduled_time:
            tz = pytz_tz(app_settings.scheduler_timezone)
            local_time = draft.scheduled_time.astimezone(tz)
            scheduled = local_time.strftime("%Y-%m-%d %H:%M %Z")

        return build_post_preview({
            "topic": draft.topic,
            "content": draft.content,
            "image_url": draft.image_url or "No image attached",
            "links": draft.links or [],
            "hashtags": draft.hashtags or [],
            "scheduled_time": scheduled,
        })

    def approve(self, draft_id: int) -> Draft:
        """
        Mark a draft as approved, ready for publishing.

        Args:
            draft_id: Draft to approve

        Returns:
            Updated Draft object

        Raises:
            ReviewError: If draft is not in a reviewable state
        """
        draft = crud.get_draft(self.db, draft_id)
        if not draft:
            raise ReviewError(f"Draft {draft_id} not found")

        if draft.status not in (PostStatus.PENDING_REVIEW, PostStatus.DRAFT):
            raise ReviewError(
                f"Draft {draft_id} cannot be approved from status '{draft.status}'. "
                f"Expected: pending_review or draft."
            )

        draft = crud.approve_draft(self.db, draft)
        log.info(f"Draft approved | id={draft_id}")
        return draft

    def cancel(self, draft_id: int) -> Draft:
        """
        Cancel a draft (soft delete — marks as cancelled, not deleted).

        Args:
            draft_id: Draft to cancel

        Returns:
            Updated Draft object

        Raises:
            ReviewError: If draft cannot be cancelled
        """
        draft = crud.get_draft(self.db, draft_id)
        if not draft:
            raise ReviewError(f"Draft {draft_id} not found")

        if draft.status == PostStatus.PUBLISHED:
            raise ReviewError(f"Draft {draft_id} is already published and cannot be cancelled")

        draft = crud.cancel_draft(self.db, draft)
        from app.memory.memory_store import memory_store
        memory_store.record_cancelled()
        log.info(f"Draft cancelled | id={draft_id}")
        return draft

    def edit_field(self, draft_id: int, field: str, value: Any) -> Draft:
        """
        Edit a specific field of a draft.
        After editing, draft returns to PENDING_REVIEW status.

        Args:
            draft_id: Draft to edit
            field: Field name to update
            value: New value

        Returns:
            Updated Draft object

        Raises:
            ReviewError: If field is not editable or draft not found
        """
        draft = crud.get_draft(self.db, draft_id)
        if not draft:
            raise ReviewError(f"Draft {draft_id} not found")

        if draft.status == PostStatus.PUBLISHED:
            raise ReviewError(f"Draft {draft_id} is already published and cannot be edited")

        EDITABLE_FIELDS = {
            "content", "hook", "body", "cta",
            "hashtags", "links", "image_url", "image_alt_text",
        }
        if field not in EDITABLE_FIELDS:
            raise ReviewError(f"Field '{field}' is not editable. Allowed: {EDITABLE_FIELDS}")

        updates = {field: value}

        # If content is edited, rebuild full_post if hook/body/cta were separated
        if field in ("hook", "body", "cta") and draft.hook and draft.body:
            hook = value if field == "hook" else (draft.hook or "")
            body = value if field == "body" else (draft.body or "")
            cta = value if field == "cta" else (draft.cta or "")
            updates["content"] = f"{hook}\n\n{body}\n\n{cta}"

        # Reset to pending review after any edit
        updates["status"] = PostStatus.PENDING_REVIEW

        draft = crud.update_draft(self.db, draft, **updates)
        log.info(f"Draft field edited | id={draft_id} | field={field}")
        return draft

    def bulk_edit(self, draft_id: int, updates: Dict[str, Any]) -> Draft:
        """
        Edit multiple fields at once.

        Args:
            draft_id: Draft to edit
            updates: Dict of {field: value} pairs

        Returns:
            Updated Draft object
        """
        draft = crud.get_draft(self.db, draft_id)
        if not draft:
            raise ReviewError(f"Draft {draft_id} not found")

        if draft.status == PostStatus.PUBLISHED:
            raise ReviewError("Published drafts cannot be edited")

        # Validate all fields first
        EDITABLE_FIELDS = {
            "content", "hook", "body", "cta",
            "hashtags", "links", "image_url", "image_alt_text",
        }
        invalid = set(updates.keys()) - EDITABLE_FIELDS
        if invalid:
            raise ReviewError(f"Non-editable fields: {invalid}. Allowed: {EDITABLE_FIELDS}")

        updates["status"] = PostStatus.PENDING_REVIEW
        draft = crud.update_draft(self.db, draft, **updates)
        log.info(f"Draft bulk-edited | id={draft_id} | fields={list(updates.keys())}")
        return draft

    def validate_ready_to_publish(self, draft: Draft) -> None:
        """
        Validate that a draft meets all requirements for publishing.

        Args:
            draft: Draft to validate

        Raises:
            ReviewError: If draft is not ready to publish
        """
        if draft.status != PostStatus.APPROVED:
            raise ReviewError(
                f"Draft must be APPROVED before publishing. Current status: '{draft.status}'. "
                f"Call POST /preview/{draft.id} and then POST /publish with confirm=true."
            )

        if not draft.content or len(draft.content.strip()) < 10:
            raise ReviewError("Draft content is empty or too short")

        from app.config import settings as app_settings
        if len(draft.content) > app_settings.post_max_length:
            raise ReviewError(
                f"Post content exceeds LinkedIn's limit. "
                f"Length: {len(draft.content)}, Max: {app_settings.post_max_length}"
            )

        log.info(f"Draft {draft.id} passed publish validation")
