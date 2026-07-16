"""
app/api/endpoints/preview.py
─────────────────────────────
GET /preview/{draft_id} — Get a full preview of a draft.
POST /preview/{draft_id}/approve — Approve a draft.
POST /preview/{draft_id}/cancel  — Cancel a draft.
"""



from fastapi import APIRouter, Depends, HTTPException, Path, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.agents.review_agent import ReviewAgent, ReviewError
from app.database.base import get_db
from app.models.schemas import DraftSchema, PreviewResponse, SuccessResponse, UploadImageRequest
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get(
    "/preview/{draft_id}",
    response_model=PreviewResponse,
    summary="Get post preview",
    description="""
    Get a full, rich preview of a LinkedIn post draft for human review.

    Displays:
    - Full post content (hook + body + CTA)
    - Hashtags
    - Image URL and source
    - Relevant links
    - Character count and estimated read time
    - Available review actions

    After reviewing, you can:
    - Approve: POST /preview/{draft_id}/approve
    - Edit: POST /edit
    - Regenerate parts: POST /regenerate
    - Cancel: POST /preview/{draft_id}/cancel
    """,
    tags=["Review"],
)
async def get_preview(
    draft_id: int = Path(..., description="ID of the draft to preview", ge=1),
    db: Session = Depends(get_db),
) -> PreviewResponse:
    """Get a rich preview of a draft for review."""
    log.info(f"GET /preview/{draft_id}")
    try:
        agent = ReviewAgent(db=db)
        return agent.get_preview(draft_id)
    except ReviewError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/preview/{draft_id}/view",
    response_class=HTMLResponse,
    summary="View post preview (HTML)",
    description="Get a beautifully formatted HTML visual preview of the draft.",
    tags=["Review"],
)
async def view_preview(
    request: Request,
    draft_id: int = Path(..., description="ID of the draft to view", ge=1),
    db: Session = Depends(get_db),
):
    """View a rich HTML preview of a draft."""
    log.info(f"GET /preview/{draft_id}/view")
    try:
        agent = ReviewAgent(db=db)
        preview_data = agent.get_preview(draft_id)
        
        # The template expects a dictionary named "draft" with specific keys
        draft_dict = preview_data.model_dump()
        
        # Map differing field names from PreviewResponse to the template variables
        draft_dict["id"] = draft_dict.get("draft_id")
        draft_dict["content"] = draft_dict.get("full_content")
        draft_dict["char_count"] = draft_dict.get("character_count")
        draft_dict["read_time"] = draft_dict.get("estimated_read_time_seconds")
        
        # Fetch created_at and ai_provider from DB since they aren't in PreviewResponse
        from app.database.models import Draft
        db_draft = db.query(Draft).filter(Draft.id == draft_id).first()
        if db_draft:
            draft_dict["created_at"] = db_draft.created_at.strftime("%Y-%m-%d %H:%M") if db_draft.created_at else ""
            draft_dict["ai_provider"] = db_draft.ai_provider or "AI"
        
        return templates.TemplateResponse(
            "preview.html", 
            {"request": request, "draft": draft_dict}
        )
    except ReviewError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/preview/{draft_id}/approve",
    response_model=DraftSchema,
    summary="Approve a draft",
    description="""
    Approve a draft for publishing.

    After approval, publish with POST /publish.

    **Status flow**: PENDING_REVIEW → APPROVED
    """,
    tags=["Review"],
)
async def approve_draft(
    draft_id: int = Path(..., description="ID of the draft to approve", ge=1),
    db: Session = Depends(get_db),
) -> DraftSchema:
    """Approve a draft for publishing."""
    log.info(f"POST /preview/{draft_id}/approve")
    try:
        agent = ReviewAgent(db=db)
        draft = agent.approve(draft_id)
        return DraftSchema.model_validate(draft)
    except ReviewError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/preview/{draft_id}/cancel",
    response_model=SuccessResponse,
    summary="Cancel a draft",
    description="Cancel a draft. It will be marked as cancelled and not published.",
    tags=["Review"],
)
async def cancel_draft(
    draft_id: int = Path(..., description="ID of the draft to cancel", ge=1),
    db: Session = Depends(get_db),
) -> SuccessResponse:
    """Cancel a draft."""
    log.info(f"POST /preview/{draft_id}/cancel")
    try:
        agent = ReviewAgent(db=db)
        agent.cancel(draft_id)
        return SuccessResponse(message=f"Draft {draft_id} cancelled successfully")
    except ReviewError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/preview/{draft_id}/upload-image",
    response_model=SuccessResponse,
    summary="Upload custom image to a draft",
    tags=["Review"],
)
async def upload_custom_image(
    request_data: UploadImageRequest,
    draft_id: int = Path(..., description="ID of the draft", ge=1),
    db: Session = Depends(get_db),
) -> SuccessResponse:
    """Upload a custom image (base64) to attach to the draft."""
    log.info(f"POST /preview/{draft_id}/upload-image")
    from app.database.models import Draft
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
        
    draft.image_url = request_data.image_base64
    draft.image_source = "gallery"
    db.commit()
    
    return SuccessResponse(message="Image updated successfully")

