"""
app/scheduler/jobs.py
──────────────────────
APScheduler job functions.
The daily job generates a post draft and notifies the user to review it.
"""

from __future__ import annotations

from app.utils.logger import get_logger

log = get_logger(__name__)


async def daily_post_generation_job() -> None:
    """
    Daily scheduled job: generate a LinkedIn post draft.

    This runs at the configured time each day.
    It generates a draft and sets it to PENDING_REVIEW.
    The user is then expected to review via the API/UI before publishing.

    Note: This function NEVER publishes automatically.
    Publishing requires explicit user approval via POST /publish.
    """
    log.info("=" * 60)
    log.info("DAILY POST GENERATION JOB STARTED")
    log.info("=" * 60)

    try:
        from app.agents.content_agent import ContentAgent
        from app.database.base import SessionLocal
        from app.database.crud import update_scheduler_job, get_or_create_scheduler_job
        from app.services.scheduler_service import DAILY_JOB_ID
        from app.utils.helpers import now_utc

        db = SessionLocal()
        try:
            # Generate the post
            agent = ContentAgent(db=db)
            draft = await agent.generate_post()

            log.info(
                f"Daily job completed | draft_id={draft.id} | topic={draft.topic} | "
                f"status={draft.status}"
            )
            log.info(
                f"REVIEW REQUIRED: Visit GET /preview/{draft.id} to review the draft"
            )
            log.info(
                f"PUBLISH: After review, call POST /publish with draft_id={draft.id} and confirm=true"
            )

            # Update scheduler job record
            job = get_or_create_scheduler_job(db, DAILY_JOB_ID, "Daily LinkedIn Post Generation")
            update_scheduler_job(
                db,
                job,
                last_run_at=now_utc(),
                run_count=job.run_count + 1,
            )

            # Send Notification
            from app.services.notification_service import NotificationService
            from app.config import settings
            
            preview_url = f"http://192.168.1.215:{settings.app_port}/api/v1/preview/{draft.id}/view"
            
            notifier = NotificationService()
            await notifier.send_message(
                message=f"New LinkedIn Draft Ready!\n\nTopic: {draft.topic}\nLength: {len(draft.content)} characters\n\nLog in to review and publish your post.",
                html_preview_url=preview_url
            )

        finally:
            db.close()

    except Exception as e:
        log.error(f"Daily post generation job FAILED: {e}", exc_info=True)
        # Don't re-raise — let APScheduler continue scheduling future runs
