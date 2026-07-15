"""
app/api/endpoints/analytics.py
────────────────────────────────
GET /analytics — Dashboard analytics summary.
GET /analytics/post/{post_id} — Per-post analytics.
POST /analytics/refresh/{post_id} — Refresh analytics from LinkedIn API.
"""



from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import crud
from app.database.base import get_db
from app.models.schemas import AnalyticsDashboard, PostAnalyticsSchema, SuccessResponse
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


@router.get(
    "/analytics",
    response_model=AnalyticsDashboard,
    summary="Get analytics dashboard",
    description="""
    Get aggregated analytics dashboard showing:
    - Posts published
    - Pending approvals
    - Drafts in progress
    - Total views, likes, comments, shares
    - Average engagement rate
    - Recent posts with their analytics
    """,
    tags=["Analytics"],
)
async def get_analytics_dashboard(db: Session = Depends(get_db)) -> AnalyticsDashboard:
    """Get analytics dashboard data."""
    log.info("GET /analytics")
    summary = crud.get_analytics_summary(db)

    # Fetch recent posts for dashboard
    from app.database.models import Post, PostAnalytics
    from app.database.base import SessionLocal
    from sqlalchemy import desc

    recent_posts_raw = (
        db.query(Post)
        .order_by(desc(Post.published_at))
        .limit(5)
        .all()
    )
    recent_posts = []
    for post in recent_posts_raw:
        analytics = post.analytics
        recent_posts.append({
            "id": post.id,
            "topic": post.topic,
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "linkedin_post_url": post.linkedin_post_url,
            "views": analytics.views if analytics else 0,
            "likes": analytics.likes if analytics else 0,
            "comments": analytics.comments if analytics else 0,
            "engagement_rate": analytics.engagement_rate if analytics else 0.0,
        })

    return AnalyticsDashboard(
        **summary,
        recent_posts=recent_posts,
    )


@router.get(
    "/analytics/post/{post_id}",
    response_model=PostAnalyticsSchema,
    summary="Get analytics for a specific post",
    tags=["Analytics"],
)
async def get_post_analytics(
    post_id: int,
    db: Session = Depends(get_db),
) -> PostAnalyticsSchema:
    """Get analytics for a specific published post."""
    from app.database.models import PostAnalytics
    analytics = db.query(PostAnalytics).filter(PostAnalytics.post_id == post_id).first()
    if not analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analytics for post {post_id} not found",
        )
    return PostAnalyticsSchema.model_validate(analytics)


@router.post(
    "/analytics/refresh/{post_id}",
    response_model=PostAnalyticsSchema,
    summary="Refresh analytics from LinkedIn",
    description="Fetch the latest analytics from LinkedIn API for a specific post.",
    tags=["Analytics"],
)
async def refresh_post_analytics(
    post_id: int,
    db: Session = Depends(get_db),
) -> PostAnalyticsSchema:
    """Refresh analytics from LinkedIn API."""
    post = crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post {post_id} not found")

    from app.services.linkedin_service import LinkedInService
    linkedin = LinkedInService()

    try:
        if post.linkedin_post_id:
            post_urn = f"urn:li:share:{post.linkedin_post_id}"
            metrics = await linkedin.get_post_analytics(post_urn)
            analytics = crud.update_analytics(db, post_id=post_id, **metrics)
            if analytics:
                return PostAnalyticsSchema.model_validate(analytics)
    except Exception as e:
        log.warning(f"Could not refresh analytics from LinkedIn: {e}")

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not fetch analytics from LinkedIn. Check your access token.",
    )
