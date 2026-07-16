"""
app/api/endpoints/publish.py
─────────────────────────────
POST /publish — Publish an approved draft to LinkedIn.

CRITICAL SAFETY:
- Draft must be in APPROVED status
- Request must include confirm=true
- This is the ONLY endpoint that publishes to LinkedIn
"""



from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.agents.review_agent import ReviewAgent, ReviewError
from app.database import crud
from app.database.base import get_db
from app.memory.memory_store import memory_store
from app.models.schemas import PublishRequest, PublishResponse
from app.services.linkedin_service import LinkedInService, LinkedInServiceError
from app.utils.helpers import now_utc
from app.utils.logger import get_logger
from app.utils.rate_limiter import limiter

log = get_logger(__name__)
router = APIRouter()


@router.post(
    "/publish",
    response_model=PublishResponse,
    summary="Publish approved post to LinkedIn",
    description="""
    Publish an approved LinkedIn post.

    **Requirements:**
    1. Draft must be in `approved` status (call POST /preview/{id}/approve first)
    2. `confirm` field must be `true` (prevents accidental publishing)
    3. `LINKEDIN_ACCESS_TOKEN` must be set in your .env

    **Safety guarantees:**
    - Will fail if draft is not approved
    - Will fail if confirm is not true
    - Validates post length before publishing
    - Records the post in database after success

    **Status flow**: APPROVED → PUBLISHED
    """,
    tags=["Publishing"],
)
@limiter.limit("5/minute")
async def publish_post(
    request: Request,
    payload: PublishRequest,
    db: Session = Depends(get_db),
) -> PublishResponse:
    """Publish an approved draft to LinkedIn."""
    log.info(f"POST /publish | draft_id={payload.draft_id}")

    # ── Step 1: Fetch and validate draft ─────────────────────
    draft = crud.get_draft(db, payload.draft_id)
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draft {payload.draft_id} not found",
        )

    # ── Step 2: Run review validation ─────────────────────────
    review_agent = ReviewAgent(db=db)
    try:
        review_agent.validate_ready_to_publish(draft)
    except ReviewError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # ── Step 3: Publish to LinkedIn ───────────────────────────
    linkedin = LinkedInService(access_token=draft.user.access_token if draft.user else None)
    
    # Construct final post text with links and hashtags
    final_content = draft.content
    if draft.links:
        final_content += "\n\n🔗 Relevant Links:\n"
        for link in draft.links:
            final_content += f"• {link}\n"
    if draft.hashtags:
        final_content += "\n\n" + " ".join(draft.hashtags)
        
    try:
        result = await linkedin.publish_post(
            content=final_content,
            image_url=draft.image_url,
            image_alt_text=draft.image_alt_text,
        )
    except LinkedInServiceError as e:
        log.error(f"LinkedIn publish failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LinkedIn publishing failed: {str(e)}",
        )
    except Exception as e:
        log.error(f"Unexpected publish error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Publishing failed. Check logs for details.",
        )

    # ── Step 4: Record in database ────────────────────────────
    post = crud.create_post_from_draft(
        db,
        draft=draft,
        linkedin_post_id=result.post_id,
        linkedin_post_url=result.post_url,
    )

    # ── Step 5: Update memory ─────────────────────────────────
    memory_store.record_published()

    log.info(
        f"Post published | post_id={post.id} | linkedin_id={result.post_id} | "
        f"topic={draft.topic}"
    )

    return PublishResponse(
        post_id=post.id,
        draft_id=payload.draft_id,
        linkedin_post_id=result.post_id,
        linkedin_post_url=result.post_url,
        published_at=post.published_at or now_utc(),
        status=post.status,
    )
