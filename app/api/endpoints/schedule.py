"""
app/api/endpoints/schedule.py
──────────────────────────────
GET /schedule  — Get current scheduler status.
POST /schedule — Update scheduler time.
POST /schedule/trigger — Trigger job immediately.
POST /schedule/pause   — Pause the scheduler.
POST /schedule/resume  — Resume the scheduler.
"""



from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import crud
from app.database.base import get_db
from app.models.schemas import ScheduleRequest, ScheduleResponse, SuccessResponse
from app.services.scheduler_service import DAILY_JOB_ID, scheduler_service
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


@router.get(
    "/schedule",
    response_model=ScheduleResponse,
    summary="Get scheduler status",
    description="Get the current scheduler configuration and next run time.",
    tags=["Scheduler"],
)
async def get_schedule(db: Session = Depends(get_db)) -> ScheduleResponse:
    """Get current scheduler state."""
    job_info = scheduler_service.get_job_info()
    job_record = crud.get_or_create_scheduler_job(db, DAILY_JOB_ID, "Daily LinkedIn Post Generation")

    from app.config import settings
    return ScheduleResponse(
        job_id=DAILY_JOB_ID,
        hour=job_record.schedule_hour if job_record.schedule_hour is not None else settings.scheduler_hour,
        minute=job_record.schedule_minute if job_record.schedule_minute is not None else settings.scheduler_minute,
        timezone=job_record.timezone or settings.scheduler_timezone,
        enabled=job_record.is_active,
        next_run_at=job_info.get("next_run_at"),
        last_run_at=job_record.last_run_at,
        run_count=job_record.run_count,
    )


@router.post(
    "/schedule",
    response_model=ScheduleResponse,
    summary="Update scheduler time",
    description="""
    Update the daily post generation schedule.

    Example: Set to 9:00 AM Karachi time:
    ```json
    {"hour": 9, "minute": 0, "timezone": "Asia/Karachi", "enabled": true}
    ```
    """,
    tags=["Scheduler"],
)
async def update_schedule(
    payload: ScheduleRequest,
    db: Session = Depends(get_db),
) -> ScheduleResponse:
    """Update the daily generation schedule."""
    log.info(f"POST /schedule | {payload.hour:02d}:{payload.minute:02d} {payload.timezone}")

    # Update DB record FIRST (this is what the poll endpoint reads, and what _register_daily_job falls back to)
    job_record = crud.get_or_create_scheduler_job(db, DAILY_JOB_ID, "Daily LinkedIn Post Generation")
    crud.update_scheduler_job(
        db,
        job_record,
        schedule_hour=payload.hour,
        schedule_minute=payload.minute,
        timezone=payload.timezone,
        is_active=payload.enabled,
    )

    import os
    if not os.environ.get("VERCEL"):
        # Only try APScheduler when running locally
        scheduler_service.reschedule(
            hour=payload.hour,
            minute=payload.minute,
            timezone=payload.timezone,
        )
        if not payload.enabled:
            scheduler_service.pause()
        else:
            scheduler_service.resume()

    job_info = scheduler_service.get_job_info()
    return ScheduleResponse(
        job_id=DAILY_JOB_ID,
        hour=payload.hour,
        minute=payload.minute,
        timezone=payload.timezone,
        enabled=payload.enabled,
        next_run_at=job_info.get("next_run_at"),
        last_run_at=job_record.last_run_at,
        run_count=job_record.run_count,
    )


@router.post(
    "/schedule/trigger",
    response_model=SuccessResponse,
    summary="Trigger generation immediately",
    description="Manually trigger the post generation job right now (useful for testing).",
    tags=["Scheduler"],
)
async def trigger_now() -> SuccessResponse:
    """Manually trigger post generation immediately."""
    log.info("POST /schedule/trigger — manual trigger")
    
    from app.scheduler.jobs import daily_post_generation_job
    try:
        # Await directly so Vercel does not kill the thread before it finishes
        await daily_post_generation_job()
    except Exception as e:
        log.error(f"Manual trigger failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger job: {e}",
        )

    return SuccessResponse(
        message="Post generation triggered and completed successfully. Check GET /history for the new draft."
    )


@router.get(
    "/schedule/cron-trigger",
    response_model=SuccessResponse,
    summary="Vercel Cron Trigger",
    description="Trigger generation from Vercel Cron. Requires GET.",
    tags=["Scheduler"],
)
async def vercel_cron_trigger() -> SuccessResponse:
    """Manually trigger post generation from Vercel Cron."""
    log.info("GET /schedule/cron-trigger — Vercel Cron triggered")

    from app.scheduler.jobs import daily_post_generation_job
    try:
        await daily_post_generation_job()
    except Exception as e:
        log.error(f"Vercel Cron job failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run cron job: {e}",
        )

    return SuccessResponse(
        message="Post generation triggered via Vercel Cron."
    )


@router.get(
    "/schedule/test-email",
    summary="Test email only (no AI generation)",
    description="Sends a test email directly using SMTP credentials. Use this to verify email works on Vercel.",
    tags=["Scheduler"],
)
async def test_email_only():
    """
    Diagnostic endpoint: sends a test email without running AI generation.
    Use this to confirm SMTP credentials are correctly set as Vercel env vars.
    """
    from app.config import settings

    creds_status = {
        "smtp_server": settings.smtp_server or "NOT SET",
        "smtp_port": settings.smtp_port,
        "smtp_user": settings.smtp_user or "NOT SET",
        "smtp_password": f"SET ({len(settings.smtp_password)} chars)" if settings.smtp_password else "NOT SET — ADD TO VERCEL ENV VARS",
        "notification_email": settings.notification_email or "NOT SET",
    }
    log.info(f"test-email diagnostic | creds={creds_status}")

    if not settings.smtp_password or not settings.smtp_user or not settings.notification_email:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "SMTP credentials missing in Vercel environment variables!",
                "fix": "Go to vercel.com → your project → Settings → Environment Variables",
                "missing_vars_to_add": {
                    "SMTP_SERVER": "smtp.gmail.com",
                    "SMTP_PORT": "465",
                    "SMTP_USER": "samratariq4544@gmail.com",
                    "SMTP_PASSWORD": "<your 16-char Gmail App Password>",
                    "NOTIFICATION_EMAIL": "samratariq4544@gmail.com",
                },
                "currently_loaded": creds_status,
            }
        )

    from app.services.notification_service import NotificationService
    notifier = NotificationService()
    sent = await notifier.send_message(
        message="Test email from LinkedIn Agent on Vercel! SMTP is working correctly.",
        html_preview_url="https://linked-in-agent-lilac.vercel.app/docs",
    )

    if sent:
        return {
            "success": True,
            "message": f"Test email sent to {settings.notification_email}! Check your inbox.",
            "credentials": creds_status,
        }
    else:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Credentials are set but email failed. Check App Password is correct.",
                "credentials": creds_status,
            }
        )



@router.get(
    "/schedule/poll",
    response_model=SuccessResponse,
    summary="GitHub Actions Polling Endpoint",
    description="Called every 5 minutes by GitHub Actions to execute dynamic scheduling.",
    tags=["Scheduler"],
)
async def schedule_poll(db: Session = Depends(get_db)) -> SuccessResponse:
    """Check if it's time to run the daily job and execute if so."""
    job_record = crud.get_or_create_scheduler_job(db, DAILY_JOB_ID, "Daily LinkedIn Post Generation")
    
    if not job_record.is_active:
        return SuccessResponse(message="Scheduler is paused. Skipping.")
        
    from datetime import datetime, timezone as dt_timezone
    import pytz
    
    from app.config import settings
    tz = pytz.timezone(job_record.timezone or settings.scheduler_timezone)
    now = datetime.now(tz)
    
    target_hour = job_record.schedule_hour if job_record.schedule_hour is not None else settings.scheduler_hour
    target_minute = job_record.schedule_minute if job_record.schedule_minute is not None else settings.scheduler_minute
    
    target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    time_diff = (now - target_time).total_seconds() / 60.0
    
    log.info(
        f"Poll check | now={now.strftime('%H:%M')} | target={target_hour:02d}:{target_minute:02d} | "
        f"diff={time_diff:.1f} min | tz={tz}"
    )
    
    # If the current time is at or after the target time today (within a 30-minute window to avoid missed fires)
    if 0 <= time_diff <= 30:
        # Check if already ran today
        if job_record.last_run_at:
            # last_run_at from SQLite is a naive UTC datetime — make it timezone-aware before comparing
            last_run_utc = job_record.last_run_at
            if last_run_utc.tzinfo is None:
                last_run_utc = last_run_utc.replace(tzinfo=dt_timezone.utc)
            last_run_local = last_run_utc.astimezone(tz)
            # If the last run happened on or after the target time today, skip
            if last_run_local >= target_time:
                log.info(f"Already ran today at {last_run_local.strftime('%H:%M')} — skipping.")
                return SuccessResponse(message="Job already ran for this target time today.")
                
        # Run it! It's past the target time and hasn't run yet today.
        log.info(f"Polling condition met! Target was {target_hour}:{target_minute}, time diff is {time_diff:.1f} mins.")
        from app.scheduler.jobs import daily_post_generation_job
        try:
            await daily_post_generation_job()
        except Exception as e:
            log.error(f"Poll trigger failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

        return SuccessResponse(message="Scheduled job triggered successfully.")

    return SuccessResponse(message=f"Current time ({now.strftime('%H:%M')}) is before target time ({target_hour:02d}:{target_minute:02d}).")


@router.get(
    "/schedule/reset",
    response_model=SuccessResponse,
    summary="Reset today's execution flag",
    description="Clears the last_run_at flag so the schedule can run again today.",
    tags=["Scheduler"],
)
async def reset_schedule(db: Session = Depends(get_db)) -> SuccessResponse:
    job_record = crud.get_or_create_scheduler_job(db, DAILY_JOB_ID, "Daily LinkedIn Post Generation")
    crud.update_scheduler_job(db, job_record, last_run_at=None)
    return SuccessResponse(message="Database cleared! You can now test the automation again today.")


@router.post(
    "/schedule/pause",
    response_model=SuccessResponse,
    summary="Pause the scheduler",
    tags=["Scheduler"],
)
async def pause_schedule() -> SuccessResponse:
    scheduler_service.pause()
    return SuccessResponse(message="Scheduler paused")


@router.post(
    "/schedule/resume",
    response_model=SuccessResponse,
    summary="Resume the scheduler",
    tags=["Scheduler"],
)
async def resume_schedule() -> SuccessResponse:
    scheduler_service.resume()
    return SuccessResponse(message="Scheduler resumed")
