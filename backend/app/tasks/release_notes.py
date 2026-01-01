from celery import Task
from app.tasks.celery_app import celery_app
from app.models.database import SessionLocal
from app.services.job_orchestrator import JobOrchestrator
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class CallbackTask(Task):
    """Task that handles database session cleanup."""
    def on_success(self, retval, task_id, args, kwargs):
        """Called on successful task completion."""
        pass
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure."""
        logger.error(f"Task {task_id} failed: {exc}")

@celery_app.task(bind=True, base=CallbackTask, name="process_release_notes_job")
def process_release_notes_job(self, job_id: str):
    """Process a release notes generation job asynchronously."""
    db = SessionLocal()
    try:
        orchestrator = JobOrchestrator(db)
        
        # Run async function in sync context
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(
            orchestrator.process_job(UUID(job_id))
        )
        
        return {"status": "completed", "job_id": job_id}
        
    except Exception as e:
        logger.error(f"Job {job_id} processing failed: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(bind=True, base=CallbackTask, name="process_webhook_event")
def process_webhook_event(self, config_id: str, event_type: str, issue_key: str, payload: dict):
    """Process webhook event asynchronously."""
    db = SessionLocal()
    try:
        orchestrator = JobOrchestrator(db)
        
        # Run async function in sync context
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(
            orchestrator.process_webhook_event(
                config_id=UUID(config_id),
                event_type=event_type,
                issue_key=issue_key,
                payload=payload
            )
        )
        
        return {"status": "completed", "config_id": config_id}
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        raise
    finally:
        db.close()