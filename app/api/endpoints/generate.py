"""
app/api/endpoints/generate.py
──────────────────────────────
POST /generate — Trigger AI post generation.
"""



from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.agents.content_agent import ContentAgent
from app.database.base import get_db
from app.models.schemas import GenerateRequest, GenerateResponse
from app.services.ai_service import AIServiceError
from app.utils.logger import get_logger
from app.utils.rate_limiter import limiter

log = get_logger(__name__)
router = APIRouter()


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a LinkedIn post",
    description="""
    Generate a new AI-powered LinkedIn post draft.

    The agent will:
    1. Auto-select a topic (or use provided topic)
    2. Generate engaging content via OpenAI/Gemini
    3. Fetch a relevant image
    4. Find 1-3 high-quality links
    5. Save as a draft in PENDING_REVIEW status

    **The post will NOT be published automatically.**
    After generation, review the draft using GET /preview/{draft_id},
    then publish using POST /publish.
    """,
    tags=["Generation"],
)
@limiter.limit("10/minute")
async def generate_post(
    request: Request,
    payload: GenerateRequest,
    db: Session = Depends(get_db),
) -> GenerateResponse:
    """Generate a new LinkedIn post draft."""
    log.info(f"POST /generate | topic={payload.topic} | provider={payload.ai_provider}")

    try:
        agent = ContentAgent(db=db)
        draft = await agent.generate_post(
            topic=payload.topic,
            ai_provider=payload.ai_provider,
            image_provider=payload.image_provider,
            style=payload.style,
            custom_instructions=payload.custom_instructions,
        )

        # Send Notification
        from app.services.notification_service import NotificationService
        from app.config import settings
        
        # Build preview URL
        app_base_url_str = str(settings.app_base_url) if settings.app_base_url else ""
        if app_base_url_str and not app_base_url_str.endswith('.loca.lt'):
            base_url = app_base_url_str.rstrip('/')
        else:
            base_url = f"http://localhost:{settings.app_port}"
            
        preview_url = f"{base_url}/api/v1/preview/{draft.id}/view"
        
        notifier = NotificationService()
        await notifier.send_message(
            message=f"New LinkedIn Draft Ready!\n\nTopic: {draft.topic}\nLength: {len(draft.content)} characters\n\nLog in to review and publish your post.",
            html_preview_url=preview_url
        )

    except AIServiceError as e:
        log.error(f"Generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI generation failed: {str(e)}. Check your API keys.",
        )
    except Exception as e:
        log.error(f"Unexpected error during generation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Post generation failed. Check logs for details.",
        )

    return GenerateResponse(
        draft_id=draft.id,
        topic=draft.topic,
        status=draft.status,
        preview_url=f"/api/v1/preview/{draft.id}/view",
    )
