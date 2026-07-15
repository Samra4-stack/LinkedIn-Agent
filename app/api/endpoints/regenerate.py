"""
app/api/endpoints/regenerate.py
─────────────────────────────────
POST /regenerate — Regenerate specific parts of a draft.
"""



from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.agents.content_agent import ContentAgent
from app.database import crud
from app.database.base import get_db
from app.models.schemas import DraftSchema, RegenerateRequest
from app.utils.logger import get_logger
from app.utils.rate_limiter import limiter

log = get_logger(__name__)
router = APIRouter()


@router.post(
    "/regenerate",
    response_model=DraftSchema,
    summary="Regenerate parts of a draft",
    description="""
    Regenerate specific parts of an existing draft without starting from scratch.

    **Regeneratable parts:**
    - `post` — Regenerate the entire post (hook + body + CTA + content)
    - `hashtags` — Generate fresh hashtags for the existing content
    - `image` — Fetch a new image from the next available provider
    - `links` — Search for new relevant links
    - `hook` — Regenerate just the opening hook
    - `cta` — Regenerate just the call-to-action

    Multiple parts can be specified in a single call.
    After regeneration, the draft returns to `pending_review` status.
    """,
    tags=["Generation"],
)
@limiter.limit("10/minute")
async def regenerate_parts(
    request: Request,
    payload: RegenerateRequest,
    db: Session = Depends(get_db),
) -> DraftSchema:
    """Regenerate specific parts of a draft."""
    log.info(f"POST /regenerate | draft_id={payload.draft_id} | parts={payload.parts}")

    draft = crud.get_draft(db, payload.draft_id)
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draft {payload.draft_id} not found",
        )

    try:
        agent = ContentAgent(db=db)
        draft = await agent.regenerate_parts(
            draft=draft,
            parts=payload.parts,
            topic_override=payload.topic,
        )
        return DraftSchema.model_validate(draft)
    except Exception as e:
        log.error(f"Regeneration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Regeneration failed: {str(e)}",
        )
