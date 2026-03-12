from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import secrets

from app.models.database import get_db, User, WebhookConfig
from app.models.schemas import (
    WebhookConfigCreate,
    WebhookConfigUpdate,
    WebhookConfigResponse,
    WebhookConfigCreateResponse,
)
from app.api.dependencies import get_current_active_user
from app.core.security import verify_jira_webhook_signature
from app.services.job_orchestrator import JobOrchestrator

router = APIRouter(prefix="/webhooks")

@router.get("/", response_model=List[WebhookConfigResponse])
async def list_webhook_configs(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all webhook configurations."""
    configs = db.query(WebhookConfig).filter(
        WebhookConfig.user_id == current_user.id
    ).all()
    return configs

@router.post("/", response_model=WebhookConfigCreateResponse)
async def create_webhook_config(
    config_data: WebhookConfigCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create new webhook configuration."""
    # Generate secret token
    secret_token = secrets.token_urlsafe(32)
    
    new_config = WebhookConfig(
        user_id=current_user.id,
        secret_token=secret_token,
        **config_data.model_dump()
    )
    
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    
    return new_config

@router.put("/{config_id}", response_model=WebhookConfigResponse)
async def update_webhook_config(
    config_id: UUID,
    config_data: WebhookConfigUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update webhook configuration."""
    config = db.query(WebhookConfig).filter(
        WebhookConfig.id == config_id,
        WebhookConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=404,
            detail="Webhook configuration not found"
        )
    
    _WEBHOOK_UPDATABLE_FIELDS = {
        "name", "trigger_events", "jql_filter",
        "instruction_set_id", "auto_publish", "is_active",
    }
    for field, value in config_data.model_dump(exclude_unset=True).items():
        if field in _WEBHOOK_UPDATABLE_FIELDS:
            setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    
    return config

@router.delete("/{config_id}")
async def delete_webhook_config(
    config_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete webhook configuration."""
    config = db.query(WebhookConfig).filter(
        WebhookConfig.id == config_id,
        WebhookConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=404,
            detail="Webhook configuration not found"
        )
    
    db.delete(config)
    db.commit()
    
    return {"message": "Webhook configuration deleted successfully"}

@router.post("/jira")
async def handle_jira_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Handle incoming Jira webhooks."""
    # Get webhook signature
    signature = request.headers.get("X-Hub-Signature")
    body = await request.body()
    
    # Verify webhook signature
    if not verify_jira_webhook_signature(body, signature):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )
    
    payload = await request.json()
    
    # Extract event information
    event_type = payload.get("webhookEvent")
    issue_key = payload.get("issue", {}).get("key")
    
    # Find matching webhook configurations
    configs = db.query(WebhookConfig).filter(
        WebhookConfig.is_active == True
    ).all()
    
    for config in configs:
        # Check if this event type should trigger
        if event_type in config.trigger_events:
            # Queue job for processing
            orchestrator = JobOrchestrator(db)
            background_tasks.add_task(
                orchestrator.process_webhook_event,
                config_id=config.id,
                event_type=event_type,
                issue_key=issue_key,
                payload=payload
            )
    
    return {"status": "accepted", "event": event_type, "issue": issue_key}