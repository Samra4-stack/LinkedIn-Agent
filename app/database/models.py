"""
app/database/models.py
──────────────────────
All SQLAlchemy ORM models for the LinkedIn AI Agent.

Tables:
    - users        : LinkedIn user profiles
    - posts        : Published LinkedIn posts
    - drafts       : AI-generated drafts awaiting review/approval
    - post_history : Complete history of all generated content
    - analytics    : Post performance metrics
    - settings     : Per-user configuration
    - scheduler_jobs: Scheduled job records
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Enums ───────────────────────────────────────────────────

class PostStatus(str, PyEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ImageSource(str, PyEnum):
    DALLE = "dalle"
    UNSPLASH = "unsplash"
    PEXELS = "pexels"
    PIXABAY = "pixabay"
    NONE = "none"


class AIProvider(str, PyEnum):
    OPENAI = "openai"
    GEMINI = "gemini"


# ─── User Model ──────────────────────────────────────────────

class User(Base):
    """Represents a LinkedIn user profile."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    linkedin_person_urn = Column(String(255), unique=True, index=True, nullable=False)
    display_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    profile_picture_url = Column(Text, nullable=True)
    access_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    drafts = relationship("Draft", back_populates="user", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False)


# ─── Draft Model ─────────────────────────────────────────────

class Draft(Base):
    """
    AI-generated content draft awaiting review.
    Goes through: DRAFT → PENDING_REVIEW → APPROVED → PUBLISHED
    """

    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Content fields
    topic = Column(String(255), nullable=False)
    hook = Column(Text, nullable=True)
    body = Column(Text, nullable=False)
    cta = Column(Text, nullable=True)
    content = Column(Text, nullable=False)  # Full assembled post
    hashtags = Column(JSON, default=list)   # List[str]
    links = Column(JSON, default=list)      # List[str]

    # Image
    image_url = Column(Text, nullable=True)
    image_source = Column(String(50), default=ImageSource.NONE)
    image_prompt = Column(Text, nullable=True)
    image_alt_text = Column(Text, nullable=True)

    # Metadata
    status = Column(String(50), default=PostStatus.DRAFT)
    ai_provider = Column(String(50), default=AIProvider.OPENAI)
    ai_model = Column(String(100), nullable=True)
    content_hash = Column(String(64), nullable=True, index=True)  # For duplicate detection
    generation_prompt = Column(Text, nullable=True)

    # Scheduling
    scheduled_time = Column(DateTime(timezone=True), nullable=True)

    # Edit tracking
    edit_count = Column(Integer, default=0)
    edit_history = Column(JSON, default=list)  # List of edit records

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    user = relationship("User", back_populates="drafts")
    post = relationship("Post", back_populates="draft", uselist=False)


# ─── Post Model ──────────────────────────────────────────────

class Post(Base):
    """A published LinkedIn post."""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=True)

    # LinkedIn metadata
    linkedin_post_id = Column(String(255), nullable=True, index=True)
    linkedin_post_url = Column(Text, nullable=True)

    # Content snapshot at publish time
    topic = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    hashtags = Column(JSON, default=list)
    links = Column(JSON, default=list)
    image_url = Column(Text, nullable=True)

    # Publishing
    published_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), default=PostStatus.PUBLISHED)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    user = relationship("User", back_populates="posts")
    draft = relationship("Draft", back_populates="post")
    analytics = relationship("PostAnalytics", back_populates="post", uselist=False)


# ─── Post History Model ───────────────────────────────────────

class PostHistory(Base):
    """
    Immutable record of all generated posts (drafts + published).
    Used by memory agent to avoid topic/content duplication.
    """

    __tablename__ = "post_history"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(255), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False, index=True)
    content_summary = Column(Text, nullable=True)  # First 200 chars
    hashtags = Column(JSON, default=list)
    status = Column(String(50), nullable=False)  # draft | published | cancelled
    generated_at = Column(DateTime(timezone=True), default=utcnow)
    published_at = Column(DateTime(timezone=True), nullable=True)


# ─── Analytics Model ─────────────────────────────────────────

class PostAnalytics(Base):
    """LinkedIn post performance analytics."""

    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)

    # Metrics (fetched from LinkedIn API)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)

    # Tracking
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationship
    post = relationship("Post", back_populates="analytics")


# ─── User Settings Model ──────────────────────────────────────

class UserSettings(Base):
    """Per-user configurable settings stored in DB."""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)

    # Scheduler
    scheduler_hour = Column(Integer, default=9)
    scheduler_minute = Column(Integer, default=0)
    scheduler_timezone = Column(String(50), default="Asia/Karachi")
    scheduler_enabled = Column(Boolean, default=True)

    # Topics
    topics = Column(JSON, default=list)          # List[str]
    preferred_hashtags = Column(JSON, default=list)  # List[str]
    writing_style = Column(String(100), default="professional")

    # Image
    preferred_image_provider = Column(String(50), default="unsplash")

    # AI
    preferred_ai_provider = Column(String(50), default="openai")
    post_language = Column(String(50), default="English")

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationship
    user = relationship("User", back_populates="settings")


# ─── Scheduler Job Model ──────────────────────────────────────

class SchedulerJob(Base):
    """Tracks APScheduler job state."""

    __tablename__ = "scheduler_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(100), unique=True, nullable=False)
    job_name = Column(String(255), nullable=False)
    trigger_type = Column(String(50), default="cron")
    schedule_hour = Column(Integer, default=9)
    schedule_minute = Column(Integer, default=0)
    timezone = Column(String(50), default="Asia/Karachi")
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    run_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
