"""
app/api/endpoints/edit.py
──────────────────────────
POST /edit — Edit a draft field.
POST /edit/bulk — Edit multiple fields at once.
"""



from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.review_agent import ReviewAgent, ReviewError
from app.database.base import get_db
from app.models.schemas import BulkEditRequest, DraftSchema, EditRequest
from app.utils.helpers import sanitize_input
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


@router.post(
    "/edit",
    response_model=DraftSchema,
    summary="Edit a draft field",
    description="""
    Edit a specific field of a draft.

    **Editable fields:**
    - `content` — Full post text
    - `hook` — Opening line(s)
    - `body` — Main content
    - `cta` — Call-to-action
    - `hashtags` — List of hashtag strings
    - `links` — List of URL strings
    - `image_url` — Image URL
    - `image_alt_text` — Image alt text

    After editing, the draft status returns to `pending_review`.
    Call GET /preview/{draft_id} again to see the updated preview.
    """,
    tags=["Editing"],
)
async def edit_draft(
    payload: EditRequest,
    db: Session = Depends(get_db),
) -> DraftSchema:
    """Edit a specific field in a draft."""
    log.info(f"POST /edit | draft_id={payload.draft_id} | field={payload.field}")

    # Sanitize string inputs
    value = payload.value
    if isinstance(value, str):
        value = sanitize_input(value, max_length=5000)

    try:
        agent = ReviewAgent(db=db)
        draft = agent.edit_field(payload.draft_id, payload.field, value)
        return DraftSchema.model_validate(draft)
    except ReviewError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/edit/bulk",
    response_model=DraftSchema,
    summary="Edit multiple draft fields at once",
    description="""
    Update multiple fields in a single request.

    Example:
    ```json
    {
      "draft_id": 1,
      "updates": {
        "hook": "New hook text",
        "hashtags": ["#AI", "#Python", "#MachineLearning"],
        "cta": "What do you think? Share in the comments!"
      }
    }
    ```
    """,
    tags=["Editing"],
)
async def bulk_edit_draft(
    payload: BulkEditRequest,
    db: Session = Depends(get_db),
) -> DraftSchema:
    """Edit multiple draft fields simultaneously."""
    log.info(f"POST /edit/bulk | draft_id={payload.draft_id} | fields={list(payload.updates.keys())}")

    # Sanitize string values
    sanitized_updates = {}
    for key, value in payload.updates.items():
        if isinstance(value, str):
            sanitized_updates[key] = sanitize_input(value, max_length=5000)
        else:
            sanitized_updates[key] = value

    try:
        agent = ReviewAgent(db=db)
        draft = agent.bulk_edit(payload.draft_id, sanitized_updates)
        return DraftSchema.model_validate(draft)
    except ReviewError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
