"""Entry points for running jobs.

The pipeline itself lives in :mod:`app.services.release_notes_pipeline`; this module keeps the
names the API routes, Celery tasks and tests call, and owns its own database session so a run
started from a request outlives that request's session.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.database import Job, SessionLocal, WebhookConfig
from app.services.release_notes_pipeline import ReleaseNotesPipeline, sanitize_job_error

logger = logging.getLogger(__name__)


class JobOrchestrator:
    """Runs the release-notes pipeline for a job."""

    def __init__(self, db: Optional[Session] = None):
        # A session passed in is used as-is (tests, Celery); otherwise one is opened per run,
        # because a request-scoped session is closed by the time a background task runs.
        self._db = db

    async def process_job(self, job_id: UUID) -> None:
        own_session = self._db is None
        db = self._db or SessionLocal()
        try:
            await ReleaseNotesPipeline(db, job_id).run()
        finally:
            if own_session:
                db.close()

    async def process_webhook_event(
        self,
        config_id: UUID,
        event_type: str,
        issue_key: str,
        payload: Dict[str, Any],
    ) -> None:
        """Create and run a job for a webhook event."""
        own_session = self._db is None
        db = self._db or SessionLocal()
        try:
            config = db.query(WebhookConfig).filter(WebhookConfig.id == config_id).first()
            if not config or not config.is_active:
                return
            job = Job(
                user_id=config.user_id,
                organization_id=config.organization_id,
                instruction_set_id=config.instruction_set_id,
                jql_query=f"key = {issue_key}",
                triggered_by="webhook",
                status="pending",
                auto_publish=config.auto_publish,
                output_filename=f"release-notes-{issue_key}.dita",
                title=f"{issue_key} release note",
            )
            db.add(job)
            db.commit()
            await ReleaseNotesPipeline(db, job.id).run()
        except Exception as exc:
            logger.error("Webhook processing failed: %s", exc, exc_info=True)
        finally:
            if own_session:
                db.close()


def _sanitize_job_error(error_msg: str) -> str:
    """Kept for callers and tests that import it from here."""
    return sanitize_job_error(error_msg)
