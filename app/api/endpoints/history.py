"""
app/api/endpoints/history.py
─────────────────────────────
GET /history         — Paginated list of all generated post history.
GET /history/drafts  — List of drafts.
GET /history/{id}    — Single post details.
"""



from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import crud
from app.database.base import get_db
from app.models.schemas import (
    DraftListResponse,
    DraftSchema,
    HistoryResponse,
    HistoryItemSchema,
    PaginationMeta,
    PostListResponse,
    PostSchema,
)
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Get post generation history",
    description="Paginated list of all generated posts (drafts + published), used for memory and deduplication.",
    tags=["History"],
)
async def get_history(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    db: Session = Depends(get_db),
) -> HistoryResponse:
    """Get paginated post history."""
    log.info(f"GET /history | skip={skip} | limit={limit}")
    records = crud.get_history(db, skip=skip, limit=limit)
    # Get total count
    from sqlalchemy import func
    from app.database.models import PostHistory
    total = db.query(func.count(PostHistory.id)).scalar() or 0

    return HistoryResponse(
        items=[HistoryItemSchema.model_validate(r) for r in records],
        meta=PaginationMeta(
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + limit) < total,
        ),
    )


@router.get(
    "/history/drafts",
    response_model=DraftListResponse,
    summary="List all drafts",
    description="List all drafts with optional status filter.",
    tags=["History"],
)
async def list_drafts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status"),
    db: Session = Depends(get_db),
) -> DraftListResponse:
    """List all drafts."""
    log.info(f"GET /history/drafts | status={status_filter}")
    drafts = crud.get_all_drafts(db, skip=skip, limit=limit, status=status_filter)
    from sqlalchemy import func
    from app.database.models import Draft
    query = db.query(func.count(Draft.id))
    if status_filter:
        query = query.filter(Draft.status == status_filter)
    total = query.scalar() or 0

    return DraftListResponse(
        items=[DraftSchema.model_validate(d) for d in drafts],
        meta=PaginationMeta(total=total, skip=skip, limit=limit, has_more=(skip + limit) < total),
    )


@router.get(
    "/history/posts",
    response_model=PostListResponse,
    summary="List published posts",
    description="List all posts that have been published to LinkedIn.",
    tags=["History"],
)
async def list_published_posts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PostListResponse:
    """List published posts."""
    posts = crud.get_all_posts(db, skip=skip, limit=limit)
    from sqlalchemy import func
    from app.database.models import Post
    total = db.query(func.count(Post.id)).scalar() or 0
    return PostListResponse(
        items=[PostSchema.model_validate(p) for p in posts],
        meta=PaginationMeta(total=total, skip=skip, limit=limit, has_more=(skip + limit) < total),
    )


@router.get(
    "/history/pending",
    response_model=DraftListResponse,
    summary="Get pending approval drafts",
    description="List all drafts that are waiting for your review and approval.",
    tags=["History"],
)
async def get_pending_drafts(db: Session = Depends(get_db)) -> DraftListResponse:
    """Get all drafts pending review."""
    drafts = crud.get_pending_drafts(db)
    return DraftListResponse(
        items=[DraftSchema.model_validate(d) for d in drafts],
        meta=PaginationMeta(total=len(drafts), skip=0, limit=len(drafts), has_more=False),
    )


@router.get(
    "/history/draft/{draft_id}",
    response_model=DraftSchema,
    summary="Get a specific draft",
    tags=["History"],
)
async def get_draft(
    draft_id: int,
    db: Session = Depends(get_db),
) -> DraftSchema:
    """Get a specific draft by ID."""
    draft = crud.get_draft(db, draft_id)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Draft {draft_id} not found")
    return DraftSchema.model_validate(draft)
