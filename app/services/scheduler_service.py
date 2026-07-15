"""
app/services/scheduler_service.py
───────────────────────────────────
APScheduler integration for daily post generation.
Manages job lifecycle and dynamic rescheduling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

DAILY_JOB_ID = "daily_post_generation"


class SchedulerService:
    """
    Manages APScheduler for the LinkedIn AI Agent.
    Runs the daily post generation job at the configured time.
    """

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
        self._is_running = False

    def start(self) -> None:
        """Start the scheduler and register the daily job."""
        if not self._is_running:
            self.scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
            self._register_daily_job()
            self.scheduler.start()
            self._is_running = True
            log.info(
                f"Scheduler started | daily job at {settings.scheduler_hour:02d}:{settings.scheduler_minute:02d} "
                f"{settings.scheduler_timezone}"
            )

    def stop(self) -> None:
        """Gracefully shutdown the scheduler."""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            log.info("Scheduler stopped")

    def _register_daily_job(self) -> None:
        """Register the daily post generation job."""
        from app.scheduler.jobs import daily_post_generation_job

        # Remove existing job if present
        if self.scheduler.get_job(DAILY_JOB_ID):
            self.scheduler.remove_job(DAILY_JOB_ID)

        self.scheduler.add_job(
            func=daily_post_generation_job,
            trigger=CronTrigger(
                hour=settings.scheduler_hour,
                minute=settings.scheduler_minute,
                timezone=settings.scheduler_timezone,
            ),
            id=DAILY_JOB_ID,
            name="Daily LinkedIn Post Generation",
            replace_existing=True,
            misfire_grace_time=3600,  # 1 hour grace period if server was down
        )
        log.info(f"Daily job registered | id={DAILY_JOB_ID}")

    def reschedule(
        self,
        hour: int,
        minute: int,
        timezone: str = settings.scheduler_timezone,
    ) -> bool:
        """
        Reschedule the daily job to a new time.

        Args:
            hour: New hour (0–23)
            minute: New minute (0–59)
            timezone: IANA timezone string

        Returns:
            True if rescheduled successfully
        """
        try:
            job = self.scheduler.get_job(DAILY_JOB_ID)
            if job:
                self.scheduler.reschedule_job(
                    DAILY_JOB_ID,
                    trigger=CronTrigger(hour=hour, minute=minute, timezone=timezone),
                )
                log.info(f"Job rescheduled | {hour:02d}:{minute:02d} {timezone}")
                return True
            else:
                log.warning(f"Job {DAILY_JOB_ID} not found, re-registering")
                self._register_daily_job()
                return True
        except Exception as e:
            log.error(f"Reschedule failed: {e}")
            return False

    def pause(self) -> bool:
        """Pause the daily job."""
        try:
            self.scheduler.pause_job(DAILY_JOB_ID)
            log.info("Daily job paused")
            return True
        except Exception as e:
            log.error(f"Pause failed: {e}")
            return False

    def resume(self) -> bool:
        """Resume the daily job."""
        try:
            self.scheduler.resume_job(DAILY_JOB_ID)
            log.info("Daily job resumed")
            return True
        except Exception as e:
            log.error(f"Resume failed: {e}")
            return False

    def trigger_now(self) -> bool:
        """
        Manually trigger the daily job immediately (for testing/on-demand).

        Returns:
            True if triggered successfully
        """
        try:
            from apscheduler.triggers.date import DateTrigger
            from datetime import timezone as tz
            self.scheduler.add_job(
                func=self._get_job_function(),
                trigger=DateTrigger(run_date=datetime.now(tz.utc)),
                id=f"{DAILY_JOB_ID}_manual_{datetime.now().timestamp():.0f}",
                name="Manual Post Generation",
                replace_existing=False,
            )
            log.info("Manual job trigger queued")
            return True
        except Exception as e:
            log.error(f"Manual trigger failed: {e}")
            return False

    def _get_job_function(self):
        from app.scheduler.jobs import daily_post_generation_job
        return daily_post_generation_job

    def get_job_info(self) -> dict:
        """Get current job status information."""
        job = self.scheduler.get_job(DAILY_JOB_ID)
        if not job:
            return {
                "job_id": DAILY_JOB_ID,
                "status": "not_registered",
                "next_run_at": None,
            }
        return {
            "job_id": job.id,
            "name": job.name,
            "status": "running" if self._is_running else "stopped",
            "next_run_at": job.next_run_time.isoformat() if job.next_run_time else None,
        }

    @property
    def is_running(self) -> bool:
        return self._is_running


# Module-level singleton
scheduler_service = SchedulerService()
