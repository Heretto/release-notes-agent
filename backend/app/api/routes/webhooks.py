import logging

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import secrets

from app.models.database import get_db, WebhookConfig
from app.models.schemas import (
    WebhookConfigCreate,
    WebhookConfigUpdate,
    WebhookConfigResponse,
    WebhookConfigCreateResponse,
)
from app.api.dependencies import get_current_active_user_with_org, CurrentUserContext
from app.core.security import verify_jira_webhook_signature, verify_webhook_signature
from app.services.job_orchestrator import JobOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks")

@router.get("", response_model=List[WebhookConfigResponse])
async def list_webhook_configs(
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """List all webhook configurations for the current organization."""
    configs = db.query(WebhookConfig).filter(
        WebhookConfig.organization_id == context.organization_id
    ).all()
    return configs

@router.post("", response_model=WebhookConfigCreateResponse)
async def create_webhook_config(
    config_data: WebhookConfigCreate,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Create new webhook configuration."""
    # Generate secret token
    secret_token = secrets.token_urlsafe(32)

    new_config = WebhookConfig(
        user_id=context.user.id,
        organization_id=context.organization_id,
        secret_token=secret_token,
        **config_data.model_dump()
    )

    db.add(new_config)
    db.commit()
    db.refresh(new_config)

    return WebhookConfigCreateResponse(
        id=new_config.id,
        name=new_config.name,
        trigger_events=list(new_config.trigger_events or []),
        jql_filter=new_config.jql_filter,
        instruction_set_id=new_config.instruction_set_id,
        auto_publish=bool(new_config.auto_publish),
        is_active=bool(new_config.is_active),
        created_at=new_config.created_at,
        secret_token=secret_token,
        webhook_path=f"/webhooks/jira/{new_config.id}",
    )

@router.put("/{config_id}", response_model=WebhookConfigResponse)
async def update_webhook_config(
    config_id: UUID,
    config_data: WebhookConfigUpdate,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Update webhook configuration."""
    config = db.query(WebhookConfig).filter(
        WebhookConfig.id == config_id,
        WebhookConfig.organization_id == context.organization_id
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
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Delete webhook configuration."""
    config = db.query(WebhookConfig).filter(
        WebhookConfig.id == config_id,
        WebhookConfig.organization_id == context.organization_id
    ).first()

    if not config:
        raise HTTPException(
            status_code=404,
            detail="Webhook configuration not found"
        )

    db.delete(config)
    db.commit()

    return {"message": "Webhook configuration deleted successfully"}

def _event_matches(config: WebhookConfig, event_type: str) -> bool:
    return bool(event_type) and event_type in (config.trigger_events or [])


@router.post("/jira/{config_id}")
async def handle_jira_webhook_for_config(
    config_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Handle a Jira webhook addressed to one configuration.

    The configuration names itself in the URL and is verified against **its own** secret, so
    a secret can only ever start work for the configuration it belongs to — and therefore
    only in that configuration's organization. Point each Jira webhook at its own URL; the
    secret to sign with is the one returned when the configuration was created.
    """
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature")

    config = db.query(WebhookConfig).filter(
        WebhookConfig.id == config_id,
        WebhookConfig.is_active == True,  # noqa: E712 — SQLAlchemy column comparison
    ).first()

    # One answer for "no such configuration" and "wrong signature". Neither tells a caller
    # holding neither the id nor the secret which of the two it got wrong.
    if config is None or not verify_webhook_signature(body, signature, config.secret_token):
        logger.warning(
            "Rejected Jira webhook for %s (%s)",
            config_id, "unknown or inactive configuration" if config is None else "bad signature",
        )
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    event_type = payload.get("webhookEvent")
    issue_key = (payload.get("issue") or {}).get("key")

    if not _event_matches(config, event_type):
        return {"status": "ignored", "event": event_type, "issue": issue_key}

    # No db: a request-scoped session is closed before a background task runs.
    background_tasks.add_task(
        JobOrchestrator().process_webhook_event,
        config_id=config.id,
        event_type=event_type,
        issue_key=issue_key,
        payload=payload,
    )
    return {"status": "accepted", "event": event_type, "issue": issue_key}


@router.post("/jira")
async def handle_jira_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Handle a Jira webhook that does not name its configuration. **Deprecated.**

    This endpoint is signed with one deployment-wide secret and fans the event out to every
    matching configuration, which across organizations means one secret can start work — and
    spend credentials — in an organization its holder has no account in. It therefore
    refuses as soon as more than one organization has an active configuration, and exists
    only so single-organization deployments keep working while their Jira webhooks are
    re-pointed at /webhooks/jira/{config_id}.
    """
    signature = request.headers.get("X-Hub-Signature")
    body = await request.body()

    if not verify_jira_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    configs = db.query(WebhookConfig).filter(
        WebhookConfig.is_active == True,  # noqa: E712 — SQLAlchemy column comparison
    ).all()

    organizations = {config.organization_id for config in configs}
    if len(organizations) > 1:
        logger.error(
            "Refused a webhook on the shared endpoint: %d organizations have active "
            "configurations, and this endpoint cannot tell which one the caller is entitled to.",
            len(organizations),
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "This deployment has webhook configurations in more than one organization, so "
                "the shared webhook endpoint is disabled. Point each Jira webhook at "
                "/webhooks/jira/{config_id} and sign it with that configuration's own secret."
            ),
        )

    payload = await request.json()
    event_type = payload.get("webhookEvent")
    issue_key = (payload.get("issue") or {}).get("key")

    logger.warning(
        "Jira webhook received on the deprecated shared endpoint; re-point it at "
        "/webhooks/jira/{config_id}"
    )

    for config in configs:
        if _event_matches(config, event_type):
            background_tasks.add_task(
                JobOrchestrator().process_webhook_event,
                config_id=config.id,
                event_type=event_type,
                issue_key=issue_key,
                payload=payload,
            )

    return {"status": "accepted", "event": event_type, "issue": issue_key}
