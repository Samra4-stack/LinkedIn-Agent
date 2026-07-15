"""
app/database/crud.py
────────────────────
CRUD (Create, Read, Update, Delete) operations for all ORM models.
All functions are synchronous and accept a SQLAlchemy Session.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database.models import (
    Draft,
    Post,
    PostAnalytics,
    PostHistory,
    PostStatus,
    SchedulerJob,
    User,
    UserSettings,
)
from app.utils.helpers import compute_hash, now_utc
from app.utils.logger import get_logger

log = get_logger(__name__)


# ─── User CRUD ───────────────────────────────────────────────

def get_or_create_user(db: Session, linkedin_person_urn: str, **kwargs) -> User:
    """Get existing user or create a new one."""
    user = db.query(User).filter(User.linkedin_person_urn == linkedin_person_urn).first()
    if not user:
        user = User(linkedin_person_urn=linkedin_person_urn, **kwargs)
        db.add(user)
        db.commit()
        db.refresh(user)
        log.info(f"Created new user | urn={linkedin_person_urn}")
    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def update_user_token(db: Session, user: User, access_token: str, expires_at: Optional[datetime] = None) -> User:
    user.access_token = access_token
    user.token_expires_at = expires_at
    db.commit()
    db.refresh(user)
    return user


# ─── Draft CRUD ──────────────────────────────────────────────

def create_draft(db: Session, **kwargs) -> Draft:
    """Create a new draft with content hash for duplicate detection."""
    content = kwargs.get("content", "")
    kwargs["content_hash"] = compute_hash(content)
    kwargs["status"] = PostStatus.PENDING_REVIEW

    draft = Draft(**kwargs)
    db.add(draft)
    db.commit()
    db.refresh(draft)

    # Also record in history
    _record_history(db, draft)

    log.info(f"Created draft | id={draft.id} | topic={draft.topic}")
    return draft


def get_draft(db: Session, draft_id: int) -> Optional[Draft]:
    return db.query(Draft).filter(Draft.id == draft_id).first()


def get_pending_drafts(db: Session) -> List[Draft]:
    """Get all drafts awaiting review."""
    return (
        db.query(Draft)
        .filter(Draft.status == PostStatus.PENDING_REVIEW)
        .order_by(desc(Draft.created_at))
        .all()
    )


def get_all_drafts(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
) -> List[Draft]:
    query = db.query(Draft)
    if status:
        query = query.filter(Draft.status == status)
    return query.order_by(desc(Draft.created_at)).offset(skip).limit(limit).all()


def update_draft(db: Session, draft: Draft, **kwargs) -> Draft:
    """Update draft fields and increment edit count."""
    # Track edit history
    edit_record = {
        "timestamp": now_utc().isoformat(),
        "fields_changed": list(kwargs.keys()),
    }
    edit_history = draft.edit_history or []
    edit_history.append(edit_record)

    for key, value in kwargs.items():
        setattr(draft, key, value)

    draft.edit_count = (draft.edit_count or 0) + 1
    draft.edit_history = edit_history

    # Recompute hash if content changed
    if "content" in kwargs:
        draft.content_hash = compute_hash(kwargs["content"])

    db.commit()
    db.refresh(draft)
    log.info(f"Updated draft | id={draft.id} | fields={list(kwargs.keys())}")
    return draft


def approve_draft(db: Session, draft: Draft) -> Draft:
    """Mark draft as approved."""
    draft.status = PostStatus.APPROVED
    db.commit()
    db.refresh(draft)
    log.info(f"Approved draft | id={draft.id}")
    return draft


def cancel_draft(db: Session, draft: Draft) -> Draft:
    """Mark draft as cancelled."""
    draft.status = PostStatus.CANCELLED
    db.commit()
    db.refresh(draft)
    log.info(f"Cancelled draft | id={draft.id}")
    return draft


def is_duplicate_content(db: Session, content_hash: str) -> bool:
    """Check if identical content hash exists in history."""
    return db.query(PostHistory).filter(PostHistory.content_hash == content_hash).first() is not None


def is_topic_recently_used(db: Session, topic: str, days: int = 7) -> bool:
    """Check if a topic was posted within the last N days."""
    cutoff = now_utc() - timedelta(days=days)
    return (
        db.query(PostHistory)
        .filter(
            PostHistory.topic == topic,
            PostHistory.generated_at >= cutoff,
        )
        .first()
        is not None
    )


# ─── Post CRUD ───────────────────────────────────────────────

def create_post_from_draft(
    db: Session,
    draft: Draft,
    linkedin_post_id: Optional[str] = None,
    linkedin_post_url: Optional[str] = None,
) -> Post:
    """Create a published post record from an approved draft."""
    post = Post(
        user_id=draft.user_id,
        draft_id=draft.id,
        linkedin_post_id=linkedin_post_id,
        linkedin_post_url=linkedin_post_url,
        topic=draft.topic,
        content=draft.content,
        hashtags=draft.hashtags,
        links=draft.links,
        image_url=draft.image_url,
        published_at=now_utc(),
        status=PostStatus.PUBLISHED,
    )
    db.add(post)

    # Update draft status
    draft.status = PostStatus.PUBLISHED
    db.commit()
    db.refresh(post)

    # Update history record
    history = db.query(PostHistory).filter(PostHistory.content_hash == draft.content_hash).first()
    if history:
        history.status = "published"
        history.published_at = post.published_at
        db.commit()

    # Create analytics placeholder
    analytics = PostAnalytics(post_id=post.id)
    db.add(analytics)
    db.commit()

    log.info(f"Created post | id={post.id} | linkedin_id={linkedin_post_id}")
    return post


def get_post(db: Session, post_id: int) -> Optional[Post]:
    return db.query(Post).filter(Post.id == post_id).first()


def get_all_posts(db: Session, skip: int = 0, limit: int = 20) -> List[Post]:
    return db.query(Post).order_by(desc(Post.published_at)).offset(skip).limit(limit).all()


# ─── Analytics CRUD ──────────────────────────────────────────

def update_analytics(
    db: Session,
    post_id: int,
    views: int = 0,
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
    clicks: int = 0,
) -> Optional[PostAnalytics]:
    """Update analytics for a post."""
    analytics = db.query(PostAnalytics).filter(PostAnalytics.post_id == post_id).first()
    if not analytics:
        return None

    analytics.views = views
    analytics.likes = likes
    analytics.comments = comments
    analytics.shares = shares
    analytics.clicks = clicks
    analytics.last_fetched_at = now_utc()

    # Recalculate engagement rate
    if views > 0:
        analytics.engagement_rate = round((likes + comments + shares) / views * 100, 2)

    db.commit()
    db.refresh(analytics)
    return analytics


def get_analytics_summary(db: Session) -> dict:
    """Return aggregate analytics summary for dashboard."""
    total_posts = db.query(func.count(Post.id)).scalar() or 0
    total_pending = db.query(func.count(Draft.id)).filter(Draft.status == PostStatus.PENDING_REVIEW).scalar() or 0
    total_drafts = db.query(func.count(Draft.id)).filter(Draft.status == PostStatus.DRAFT).scalar() or 0
    total_approved = db.query(func.count(Draft.id)).filter(Draft.status == PostStatus.APPROVED).scalar() or 0

    analytics_agg = db.query(
        func.sum(PostAnalytics.views).label("total_views"),
        func.sum(PostAnalytics.likes).label("total_likes"),
        func.sum(PostAnalytics.comments).label("total_comments"),
        func.sum(PostAnalytics.shares).label("total_shares"),
        func.avg(PostAnalytics.engagement_rate).label("avg_engagement"),
    ).first()

    return {
        "posts_published": total_posts,
        "pending_approval": total_pending,
        "drafts": total_drafts,
        "approved": total_approved,
        "total_views": int(analytics_agg.total_views or 0),
        "total_likes": int(analytics_agg.total_likes or 0),
        "total_comments": int(analytics_agg.total_comments or 0),
        "total_shares": int(analytics_agg.total_shares or 0),
        "avg_engagement_rate": round(float(analytics_agg.avg_engagement or 0), 2),
    }


# ─── Settings CRUD ───────────────────────────────────────────

def get_settings(db: Session, user_id: Optional[int] = None) -> Optional[UserSettings]:
    if user_id:
        return db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    return db.query(UserSettings).first()


def get_or_create_settings(db: Session, user_id: Optional[int] = None) -> UserSettings:
    settings_record = get_settings(db, user_id)
    if not settings_record:
        settings_record = UserSettings(user_id=user_id)
        db.add(settings_record)
        db.commit()
        db.refresh(settings_record)
    return settings_record


def update_settings(db: Session, settings_record: UserSettings, **kwargs) -> UserSettings:
    for key, value in kwargs.items():
        if hasattr(settings_record, key):
            setattr(settings_record, key, value)
    db.commit()
    db.refresh(settings_record)
    return settings_record


# ─── History CRUD ────────────────────────────────────────────

def _record_history(db: Session, draft: Draft) -> None:
    """Internal: record draft in immutable history."""
    history = PostHistory(
        topic=draft.topic,
        content_hash=draft.content_hash or "",
        content_summary=draft.content[:200] if draft.content else "",
        hashtags=draft.hashtags or [],
        status="draft",
        generated_at=now_utc(),
    )
    db.add(history)
    db.commit()


def get_recent_topics(db: Session, days: int = 30) -> List[str]:
    """Return list of topics used in the last N days."""
    cutoff = now_utc() - timedelta(days=days)
    records = (
        db.query(PostHistory.topic)
        .filter(PostHistory.generated_at >= cutoff)
        .distinct()
        .all()
    )
    return [r.topic for r in records]


def get_history(db: Session, skip: int = 0, limit: int = 50) -> List[PostHistory]:
    return db.query(PostHistory).order_by(desc(PostHistory.generated_at)).offset(skip).limit(limit).all()


# ─── Scheduler CRUD ──────────────────────────────────────────

def get_or_create_scheduler_job(db: Session, job_id: str, job_name: str) -> SchedulerJob:
    job = db.query(SchedulerJob).filter(SchedulerJob.job_id == job_id).first()
    if not job:
        job = SchedulerJob(job_id=job_id, job_name=job_name)
        db.add(job)
        db.commit()
        db.refresh(job)
    return job


def update_scheduler_job(db: Session, job: SchedulerJob, **kwargs) -> SchedulerJob:
    for key, value in kwargs.items():
        if hasattr(job, key):
            setattr(job, key, value)
    db.commit()
    db.refresh(job)
    return job
