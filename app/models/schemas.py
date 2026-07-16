"""
app/models/schemas.py
─────────────────────
Pydantic v2 schemas for all API request and response payloads.
These are separate from SQLAlchemy models to maintain clean separation
between database layer and API layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ─── Common ──────────────────────────────────────────────────

class SuccessResponse(BaseModel):
    """Generic success wrapper."""
    success: bool = True
    message: str = "Operation completed successfully"
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Generic error wrapper."""
    success: bool = False
    error: str
    detail: Optional[str] = None


class PaginationMeta(BaseModel):
    total: int
    skip: int
    limit: int
    has_more: bool


# ─── Generation ──────────────────────────────────────────────

class GenerateRequest(BaseModel):
    """Request to generate a new LinkedIn post."""
    topic: Optional[str] = Field(
        default=None,
        description="Topic for the post. If None, one is auto-selected from configured topics.",
        json_schema_extra={"example": "Artificial Intelligence"},
    )
    ai_provider: Optional[str] = Field(
        default=None,
        description="Override AI provider: 'openai' or 'gemini'",
        json_schema_extra={"example": "openai"},
    )
    image_provider: Optional[str] = Field(
        default=None,
        description="Override image provider: 'unsplash', 'pexels', 'pixabay', 'dalle'",
        json_schema_extra={"example": "unsplash"},
    )
    style: Optional[str] = Field(
        default="professional",
        description="Writing style: professional | casual | storytelling | educational",
        json_schema_extra={"example": "professional"},
    )
    custom_instructions: Optional[str] = Field(
        default=None,
        description="Additional instructions for the AI",
        max_length=500,
    )

    @field_validator("ai_provider")
    @classmethod
    def validate_ai_provider(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ("openai", "gemini", "groq"):
            raise ValueError("ai_provider must be 'openai', 'gemini', or 'groq'")
        return v


class GenerateResponse(BaseModel):
    """Response after generating a post draft."""
    draft_id: int
    topic: str
    status: str
    message: str = "Post generated successfully. Please review and approve."
    preview_url: str = Field(description="Endpoint to fetch full preview")


# ─── Draft ───────────────────────────────────────────────────

class DraftSchema(BaseModel):
    """Full draft data."""
    model_config = {"from_attributes": True}

    id: int
    topic: str
    hook: Optional[str] = None
    body: Optional[str] = None
    cta: Optional[str] = None
    content: str
    hashtags: List[str] = []
    links: List[str] = []
    image_url: Optional[str] = None
    image_source: Optional[str] = None
    image_alt_text: Optional[str] = None
    status: str
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    edit_count: int = 0
    created_at: datetime
    updated_at: datetime


class DraftListResponse(BaseModel):
    """Paginated list of drafts."""
    items: List[DraftSchema]
    meta: PaginationMeta


# ─── Preview ─────────────────────────────────────────────────

class PreviewResponse(BaseModel):
    """Rich post preview for human review."""
    draft_id: int
    topic: str
    hook: Optional[str] = None
    body: Optional[str] = None
    cta: Optional[str] = None
    full_content: str
    hashtags: List[str] = []
    links: List[str] = []
    image_url: Optional[str] = None
    image_source: Optional[str] = None
    image_alt_text: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    status: str
    edit_count: int = 0
    character_count: int = 0
    estimated_read_time_seconds: int = 0

    # Review options presented to user
    review_options: List[str] = Field(
        default=[
            "1. Publish",
            "2. Edit Content",
            "3. Change Image",
            "4. Regenerate Post",
            "5. Regenerate Hashtags",
            "6. Change Links",
            "7. Cancel",
        ]
    )

class UploadImageRequest(BaseModel):
    """Payload for uploading a base64 image from the gallery."""
    image_base64: str = Field(..., description="Base64 encoded string of the compressed image")


# ─── Edit ────────────────────────────────────────────────────

class EditRequest(BaseModel):
    """Request to edit a draft field."""
    draft_id: int
    field: str = Field(
        description="Field to edit: content | hook | body | cta | hashtags | links | image_url",
        json_schema_extra={"example": "content"},
    )
    value: Any = Field(description="New value for the field")

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        allowed = {"content", "hook", "body", "cta", "hashtags", "links", "image_url", "image_alt_text"}
        if v not in allowed:
            raise ValueError(f"field must be one of: {', '.join(sorted(allowed))}")
        return v


class BulkEditRequest(BaseModel):
    """Edit multiple fields at once."""
    draft_id: int
    updates: Dict[str, Any] = Field(
        description="Dictionary of field → new value pairs",
        json_schema_extra={"example": {"hook": "New hook text", "hashtags": ["#AI", "#Python"]}},
    )


# ─── Regenerate ──────────────────────────────────────────────

class RegenerateRequest(BaseModel):
    """Request to regenerate specific parts of a draft."""
    draft_id: int
    parts: List[str] = Field(
        description="Parts to regenerate: post | hashtags | image | links | hook | cta",
        json_schema_extra={"example": ["hashtags"]},
    )
    topic: Optional[str] = Field(default=None, description="Override topic (for full post regeneration)")

    @field_validator("parts")
    @classmethod
    def validate_parts(cls, v: List[str]) -> List[str]:
        allowed = {"post", "hashtags", "image", "links", "hook", "cta"}
        invalid = set(v) - allowed
        if invalid:
            raise ValueError(f"Invalid parts: {invalid}. Allowed: {allowed}")
        return v


# ─── Publish ─────────────────────────────────────────────────

class PublishRequest(BaseModel):
    """Request to publish an approved draft."""
    draft_id: int
    confirm: bool = Field(
        default=False,
        description="Must be True to confirm publishing. Safety check.",
    )

    @field_validator("confirm")
    @classmethod
    def validate_confirm(cls, v: bool) -> bool:
        if not v:
            raise ValueError("confirm must be True to publish. This prevents accidental publishing.")
        return v


class PublishResponse(BaseModel):
    """Response after publishing a post."""
    post_id: int
    draft_id: int
    linkedin_post_id: Optional[str] = None
    linkedin_post_url: Optional[str] = None
    published_at: datetime
    status: str
    message: str = "Post published successfully to LinkedIn"


# ─── Schedule ────────────────────────────────────────────────

class ScheduleRequest(BaseModel):
    """Update the daily scheduler configuration."""
    hour: int = Field(ge=0, le=23, description="Hour of day (0–23)")
    minute: int = Field(ge=0, le=59, description="Minute (0–59)")
    timezone: str = Field(default="Asia/Karachi", description="IANA timezone string")
    enabled: bool = Field(default=True)


class ScheduleResponse(BaseModel):
    """Current scheduler state."""
    job_id: str
    hour: int
    minute: int
    timezone: str
    enabled: bool
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    run_count: int = 0


# ─── Analytics ───────────────────────────────────────────────

class PostAnalyticsSchema(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    post_id: int
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0
    engagement_rate: float = 0.0
    last_fetched_at: Optional[datetime] = None


class AnalyticsDashboard(BaseModel):
    """Aggregated analytics dashboard data."""
    posts_published: int = 0
    pending_approval: int = 0
    drafts: int = 0
    approved: int = 0
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    avg_engagement_rate: float = 0.0
    recent_posts: List[Dict[str, Any]] = []


# ─── Post ────────────────────────────────────────────────────

class PostSchema(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    topic: str
    content: str
    hashtags: List[str] = []
    links: List[str] = []
    image_url: Optional[str] = None
    linkedin_post_id: Optional[str] = None
    linkedin_post_url: Optional[str] = None
    published_at: Optional[datetime] = None
    status: str
    analytics: Optional[PostAnalyticsSchema] = None


class PostListResponse(BaseModel):
    items: List[PostSchema]
    meta: PaginationMeta


# ─── History ─────────────────────────────────────────────────

class HistoryItemSchema(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    topic: str
    content_summary: Optional[str] = None
    hashtags: List[str] = []
    status: str
    generated_at: datetime
    published_at: Optional[datetime] = None


class HistoryResponse(BaseModel):
    items: List[HistoryItemSchema]
    meta: PaginationMeta


# ─── Settings ────────────────────────────────────────────────

class SettingsSchema(BaseModel):
    model_config = {"from_attributes": True}

    scheduler_hour: int = 9
    scheduler_minute: int = 0
    scheduler_timezone: str = "Asia/Karachi"
    scheduler_enabled: bool = True
    topics: List[str] = []
    preferred_hashtags: List[str] = []
    writing_style: str = "professional"
    preferred_image_provider: str = "unsplash"
    preferred_ai_provider: str = "groq"
    post_language: str = "English"


class UpdateSettingsRequest(BaseModel):
    """Partial settings update."""
    scheduler_hour: Optional[int] = Field(default=None, ge=0, le=23)
    scheduler_minute: Optional[int] = Field(default=None, ge=0, le=59)
    scheduler_timezone: Optional[str] = None
    scheduler_enabled: Optional[bool] = None
    topics: Optional[List[str]] = None
    preferred_hashtags: Optional[List[str]] = None
    writing_style: Optional[str] = None
    preferred_image_provider: Optional[str] = None
    preferred_ai_provider: Optional[str] = None
    post_language: Optional[str] = None
