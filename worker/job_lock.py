from __future__ import annotations

from datetime import datetime, timedelta, timezone
from logging import getLogger

from database.models import ScheduledJob
from database.session import SessionLocal

logger = getLogger(__name__)


def acquire_job_lock(job_name: str, lock_minutes: int) -> bool:
    """Prevent overlapping executions using DB-backed locks."""
    session = SessionLocal()
    now = datetime.now(timezone.utc)
    lock_until = now + timedelta(minutes=lock_minutes)
    try:
        job = session.query(ScheduledJob).filter_by(job_name=job_name).first()
        if job is None:
            job = ScheduledJob(job_name=job_name, status="idle")
            session.add(job)
            session.flush()
        if job.overlap_lock_until and job.overlap_lock_until > now:
            logger.info("job_skipped_overlap", extra={"job_name": job_name})
            return False
        job.status = "running"
        job.last_started_at = now
        job.overlap_lock_until = lock_until
        session.commit()
        return True
    finally:
        session.close()


def release_job_lock(job_name: str, *, success: bool, error: str | None = None) -> None:
    session = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        job = session.query(ScheduledJob).filter_by(job_name=job_name).first()
        if job is None:
            return
        job.status = "success" if success else "failed"
        job.last_finished_at = now
        job.last_error = error
        job.overlap_lock_until = None
        job.run_count = (job.run_count or 0) + 1
        session.commit()
    finally:
        session.close()
