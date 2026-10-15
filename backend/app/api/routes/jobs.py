"""Jobs: running the pipeline, and the workspace a person finishes the result in."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import CurrentUserContext, get_current_active_user_with_org
from app.config import get_settings
from app.core.security import decrypt_credentials
from app.models.database import (
    ChunkingStrategy, Credential, CredentialType, HistoryEvent, InstructionSet, ItemStatus, Job,
    JobArtifact, JobRequest, JobStatus, JobTrigger,
    ReleaseNoteItem, ReleaseNoteItemReference, ReleaseNoteTopic, get_db,
)
from app.models.schemas import (
    ChatMessageResponse, ChatSendRequest, ChatSendResponse, ItemReferenceCreate, ItemReferenceResponse,
    JiraPreviewRequest, JiraPreviewResponse, JobArtifactResponse, JobCreate, JobIssueResponse, JobResponse,
    JobStatusEnum, ReassembleRequest, ReleaseNoteItemDetailResponse, ReleaseNoteItemResponse,
    ReleaseNoteItemUpdate, ReleaseNoteTopicResponse,
)
from app.services.job_orchestrator import JobOrchestrator
from app.services.topic_assembler import FragmentError
from app.services.workspace_chat import ChatUnavailable, WorkspaceChat
from app.services.workspace_service import (
    PublishError, assemble_job_topics, chat_message_to_response, issue_to_response, item_to_detail,
    item_to_response, job_to_response, move_item, publish_topics, record_history, set_item_content,
    topic_to_response,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs")

ACTIVE_STATUSES = (JobStatus.PENDING, JobStatus.RUNNING)


# ── Helpers ──────────────────────────────────────────────────────────────────────────

def _job_query(db: Session, organization_id):
    return db.query(Job).options(
        selectinload(Job.items).selectinload(ReleaseNoteItem.issue_links),
        selectinload(Job.issues),
        selectinload(Job.topics),
        selectinload(Job.instruction_set),
    ).filter(Job.organization_id == organization_id)


def _get_job(job_id: UUID, context: CurrentUserContext, db: Session) -> Job:
    job = _job_query(db, context.organization_id).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _get_item(job: Job, item_id: UUID) -> ReleaseNoteItem:
    item = next((i for i in job.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release note not found")
    return item


def _require_idle(job: Job) -> None:
    if job.status in ACTIVE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The job is running. Wait for it to finish before editing its release notes.",
        )


def _queue_run(job: Job, background_tasks: BackgroundTasks, db: Session) -> None:
    job.status = JobStatus.PENDING
    job.error_message = None
    job.stage = None
    job.stage_message = "Queued"
    db.commit()
    background_tasks.add_task(JobOrchestrator().process_job, job_id=job.id)


def _reassemble(db: Session, job: Job) -> None:
    try:
        assemble_job_topics(db, job)
    except FragmentError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="The topic would not be valid DITA: " + "; ".join(exc.errors[:3]))


def _safe_filename(name: str) -> str:
    from pathlib import PurePosixPath
    safe = PurePosixPath(name or "download").name.replace("\\", "")
    return re.sub(r"[^\w.\-]", "_", safe).strip("_.") or "download"


# ── Jobs ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[JobResponse])
async def list_jobs(
    status_filter: Optional[JobStatusEnum] = None,
    limit: int = 50,
    offset: int = 0,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """List jobs with optional filtering."""
    settings = get_settings()
    limit = min(limit, settings.max_query_limit)
    query = _job_query(db, context.organization_id)
    if status_filter:
        query = query.filter(Job.status == status_filter)
    jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
    return [job_to_response(job) for job in jobs]


@router.post("", response_model=JobResponse)
async def create_job(
    job_data: JobCreate,
    background_tasks: BackgroundTasks,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """Create a job and start its first run."""
    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == job_data.instruction_set_id,
        InstructionSet.organization_id == context.organization_id,
    ).first()
    if not instruction_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction set not found")
    if instruction_set.writer_agent_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The instruction set has no writer agent. Pick one before running a job.",
        )

    if job_data.ai_credential_id:
        ai_credential = db.query(Credential).filter(
            Credential.id == job_data.ai_credential_id,
            Credential.organization_id == context.organization_id,
            Credential.type.in_([CredentialType.GEMINI, CredentialType.OPENAI, CredentialType.ANTHROPIC]),
        ).first()
        if not ai_credential:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI credential not found")

    job = Job(
        user_id=context.user.id,
        organization_id=context.organization_id,
        instruction_set_id=job_data.instruction_set_id,
        ai_credential_id=job_data.ai_credential_id,
        title=(job_data.title or "").strip() or None,
        jql_query=job_data.jql_query,
        output_filename=job_data.output_filename,
        heretto_folder_id=job_data.heretto_folder_id,
        auto_publish=job_data.publish_to_heretto,
        max_tickets=job_data.max_tickets,
        chunking_strategy=job_data.chunking_strategy or instruction_set.chunking_strategy or ChunkingStrategy.SINGLE,
        triggered_by=JobTrigger.MANUAL,
        status=JobStatus.PENDING,
        stage_message="Queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(JobOrchestrator().process_job, job_id=job.id)
    return job_to_response(_get_job(job.id, context, db))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    return job_to_response(_get_job(job_id, context, db))


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    if job.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot cancel job with status: {job.status.value}")
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Job cancelled successfully"}


@router.post("/{job_id}/rerun", response_model=JobResponse)
async def rerun_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """Run the pipeline again on this job: unchanged issues keep their notes, changes are recorded."""
    job = _get_job(job_id, context, db)
    _require_idle(job)
    _queue_run(job, background_tasks, db)
    return job_to_response(job)


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """Retry a failed job (the same as a rerun)."""
    job = _get_job(job_id, context, db)
    if job.status != JobStatus.FAILED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only retry failed jobs")
    _queue_run(job, background_tasks, db)
    return job_to_response(job)


@router.delete("/{job_id}")
async def delete_job(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    db.delete(job)
    db.commit()
    return {"message": "Job deleted successfully", "job_id": str(job_id)}


@router.get("/{job_id}/requests")
async def get_job_requests(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """The run log: every Jira, agent and Heretto call the pipeline made."""
    job = _get_job(job_id, context, db)
    requests = db.query(JobRequest).filter(JobRequest.job_id == job.id).order_by(JobRequest.created_at).all()
    formatted = []
    for req in requests:
        def parse(raw):
            try:
                return json.loads(raw) if raw else {}
            except (json.JSONDecodeError, ValueError):
                return {}
        formatted.append({
            "id": str(req.id), "type": req.request_type, "status": req.status,
            "timestamp": req.created_at.isoformat() if req.created_at else None,
            "duration_ms": req.duration_ms, "error_message": req.error_message,
            "request_data": parse(req.request_data), "response_data": parse(req.response_data),
        })
    return formatted


# ── Artifacts (download of the assembled topics) ─────────────────────────────────────

@router.get("/{job_id}/artifacts", response_model=List[JobArtifactResponse])
async def get_job_artifacts(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    return db.query(JobArtifact).filter(JobArtifact.job_id == job.id).order_by(JobArtifact.created_at).all()


def _get_artifact(job: Job, artifact_id: UUID, db: Session) -> JobArtifact:
    artifact = db.query(JobArtifact).filter(JobArtifact.id == artifact_id, JobArtifact.job_id == job.id).first()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return artifact


@router.get("/{job_id}/artifacts/{artifact_id}/content")
async def get_artifact_content(
    job_id: UUID,
    artifact_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    artifact = _get_artifact(_get_job(job_id, context, db), artifact_id, db)
    is_xml = artifact.artifact_type == "dita" or artifact.filename.endswith((".dita", ".xml"))
    return {"filename": artifact.filename, "content": artifact.content,
            "content_type": "application/xml" if is_xml else "text/plain"}


@router.get("/{job_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    job_id: UUID,
    artifact_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    artifact = _get_artifact(_get_job(job_id, context, db), artifact_id, db)
    is_xml = artifact.artifact_type == "dita" or artifact.filename.endswith((".dita", ".xml"))
    safe_name = _safe_filename(artifact.filename)
    return Response(
        content=artifact.content,
        media_type="application/xml" if is_xml else "text/plain",
        headers={"Content-Disposition": f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{quote(safe_name)}"},
    )


@router.delete("/{job_id}/artifacts")
async def delete_all_job_artifacts(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    deleted = db.query(JobArtifact).filter(JobArtifact.job_id == job.id).delete()
    db.commit()
    return {"message": f"Successfully deleted {deleted} artifacts", "job_id": str(job_id), "deleted_count": deleted}


@router.delete("/{job_id}/artifacts/{artifact_id}")
async def delete_job_artifact(
    job_id: UUID,
    artifact_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    artifact = _get_artifact(_get_job(job_id, context, db), artifact_id, db)
    filename = artifact.filename
    db.delete(artifact)
    db.commit()
    return {"message": f"Successfully deleted artifact: {filename}", "artifact_id": str(artifact_id), "filename": filename}


# ── Workspace: issues and notes ──────────────────────────────────────────────────────

@router.get("/{job_id}/issues", response_model=List[JobIssueResponse])
async def list_job_issues(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    return [issue_to_response(i) for i in sorted(job.issues, key=lambda i: i.issue_key)]


@router.get("/{job_id}/items", response_model=List[ReleaseNoteItemResponse])
async def list_job_items(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    return [item_to_response(i) for i in sorted(job.items, key=lambda i: i.position)]


@router.get("/{job_id}/items/{item_id}", response_model=ReleaseNoteItemDetailResponse)
async def get_job_item(
    job_id: UUID,
    item_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    return item_to_detail(_get_item(job, item_id))


@router.patch("/{job_id}/items/{item_id}", response_model=ReleaseNoteItemDetailResponse)
async def update_job_item(
    job_id: UUID,
    item_id: UUID,
    update: ReleaseNoteItemUpdate,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """Edit a note: headline, summary, DITA content, status, group, or clear its attention flag."""
    job = _get_job(job_id, context, db)
    _require_idle(job)
    item = _get_item(job, item_id)
    user_id = context.user.id
    changed = False

    if update.title is not None and update.title.strip() != item.title:
        previous = item.title
        item.title = update.title.strip()
        item.user_edited = True
        record_history(db, item, HistoryEvent.CONTENT_EDITED, f"Headline changed from “{previous}” to “{item.title}”",
                       actor="user", user_id=user_id, details={"field": "title", "from": previous, "to": item.title})
        changed = True
    if update.summary is not None and update.summary.strip() != (item.summary or "").strip():
        previous = item.summary
        item.summary = update.summary.strip()
        item.user_edited = True
        record_history(db, item, HistoryEvent.CONTENT_EDITED, "Summary edited", actor="user", user_id=user_id,
                       details={"field": "summary", "from": previous, "to": item.summary})
        changed = True
    if update.dita_content is not None:
        try:
            if set_item_content(db, item, update.dita_content, actor="user", user_id=user_id):
                changed = True
        except FragmentError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail={"message": "The fragment is not valid DITA", "errors": exc.errors})
    if update.status is not None and update.status != item.status:
        previous = item.status
        item.status = update.status
        record_history(db, item, HistoryEvent.STATUS_CHANGED, f"Status changed from {previous} to {item.status}",
                       actor="user", user_id=user_id, details={"from": previous, "to": item.status})
        changed = True
    if update.group_name is not None and (update.group_name.strip() or None) != item.group_name:
        previous = item.group_name
        move_item(job, item, update.group_name.strip(), None)
        record_history(db, item, HistoryEvent.MOVED, f"Moved to group “{item.group_name or '(none)'}”",
                       actor="user", user_id=user_id, details={"from_group": previous, "to_group": item.group_name})
        changed = True
    if update.clear_attention and item.needs_attention:
        item.needs_attention = False
        item.attention_reason = None
        record_history(db, item, HistoryEvent.FLAGGED, "Attention flag cleared", actor="user", user_id=user_id)

    if changed:
        _reassemble(db, job)
    db.commit()
    db.refresh(item)
    return item_to_detail(item)


class ItemMoveRequest(BaseModel):
    group_name: Optional[str] = Field(None, max_length=255)
    position: Optional[int] = Field(None, ge=1)


@router.post("/{job_id}/items/{item_id}/move", response_model=List[ReleaseNoteItemResponse])
async def move_job_item(
    job_id: UUID,
    item_id: UUID,
    move: ItemMoveRequest,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """Reorder a note (1-based position within its group) and/or change its group."""
    job = _get_job(job_id, context, db)
    _require_idle(job)
    item = _get_item(job, item_id)
    previous = item.group_name
    move_item(job, item, move.group_name, move.position)
    where = f"to group “{item.group_name}”" if move.group_name is not None and move.group_name != previous else "within its group"
    if move.position:
        where += f" at position {move.position}"
    record_history(db, item, HistoryEvent.MOVED, f"Moved {where}", actor="user", user_id=context.user.id,
                   details={"from_group": previous, "to_group": item.group_name, "position": move.position})
    _reassemble(db, job)
    db.commit()
    return [item_to_response(i) for i in sorted(job.items, key=lambda i: i.position)]


@router.post("/{job_id}/items/{item_id}/references", response_model=ItemReferenceResponse)
async def add_item_reference(
    job_id: UUID,
    item_id: UUID,
    data: ItemReferenceCreate,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    item = _get_item(job, item_id)
    url = data.url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The link must start with http:// or https://")
    reference = ReleaseNoteItemReference(item_id=item.id, user_id=context.user.id, url=url,
                                         label=(data.label or "").strip() or None)
    db.add(reference)
    record_history(db, item, HistoryEvent.REFERENCE_ADDED, f"Link added: {reference.label or url}",
                   actor="user", user_id=context.user.id, details={"url": url, "label": reference.label})
    db.commit()
    db.refresh(reference)
    return ItemReferenceResponse(id=reference.id, url=reference.url, label=reference.label,
                                 user_id=reference.user_id, created_at=reference.created_at)


@router.delete("/{job_id}/items/{item_id}/references/{reference_id}")
async def delete_item_reference(
    job_id: UUID,
    item_id: UUID,
    reference_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    item = _get_item(job, item_id)
    reference = next((r for r in item.references if r.id == reference_id), None)
    if reference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    label = reference.label or reference.url
    db.delete(reference)
    record_history(db, item, HistoryEvent.REFERENCE_REMOVED, f"Link removed: {label}",
                   actor="user", user_id=context.user.id, details={"url": reference.url})
    db.commit()
    return {"message": "Link removed"}


# ── Workspace: topics ────────────────────────────────────────────────────────────────

@router.get("/{job_id}/topics", response_model=List[ReleaseNoteTopicResponse])
async def list_job_topics(
    job_id: UUID,
    render: bool = True,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    return [topic_to_response(t, with_html=render) for t in sorted(job.topics, key=lambda t: t.position)]


@router.post("/{job_id}/topics/reassemble", response_model=List[ReleaseNoteTopicResponse])
async def reassemble_job_topics(
    job_id: UUID,
    data: ReassembleRequest,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """Re-split the notes into topics with another chunking strategy."""
    job = _get_job(job_id, context, db)
    _require_idle(job)
    try:
        assemble_job_topics(db, job, data.chunking_strategy)
    except FragmentError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="The topic would not be valid DITA: " + "; ".join(exc.errors[:3]))
    db.commit()
    return [topic_to_response(t) for t in sorted(job.topics, key=lambda t: t.position)]


@router.get("/{job_id}/topics/{topic_id}/download")
async def download_topic(
    job_id: UUID,
    topic_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    topic = next((t for t in job.topics if t.id == topic_id), None)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    safe_name = _safe_filename(topic.filename)
    return Response(
        content=topic.dita_content, media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{quote(safe_name)}"},
    )


class PublishResult(BaseModel):
    success: bool
    document_id: Optional[str] = None
    message: str


@router.post("/{job_id}/publish", response_model=List[PublishResult])
async def publish_job(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """Create or update every topic in Heretto."""
    job = _get_job(job_id, context, db)
    _require_idle(job)
    if not job.topics:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There are no topics to publish yet.")
    try:
        results = await publish_topics(db, job)
    except PublishError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return [PublishResult(success=r.success, document_id=r.document_id, message=r.message) for r in results]


# ── Workspace: chat ──────────────────────────────────────────────────────────────────

@router.get("/{job_id}/chat", response_model=List[ChatMessageResponse])
async def list_chat_messages(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    return [chat_message_to_response(m) for m in sorted(job.chat_messages, key=lambda m: m.created_at or 0)]


@router.post("/{job_id}/chat", response_model=ChatSendResponse)
async def send_chat_message(
    job_id: UUID,
    data: ChatSendRequest,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """Ask the writer agent to change or explain the release notes."""
    job = _get_job(job_id, context, db)
    _require_idle(job)
    try:
        return await WorkspaceChat(db, job, context.user.id).send(data.message, data.selected_item_id)
    except ChatUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{job_id}/chat")
async def clear_chat(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, context, db)
    for message in list(job.chat_messages):
        db.delete(message)
    db.commit()
    return {"message": "Chat cleared"}


# ── Jira preview ─────────────────────────────────────────────────────────────────────

@router.post("/preview", response_model=JiraPreviewResponse)
async def preview_jira_query(
    preview_request: JiraPreviewRequest,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    credential = db.query(Credential).filter(
        Credential.id == preview_request.credential_id,
        Credential.organization_id == context.organization_id,
        Credential.type == "jira",
    ).first()
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jira credential not found")

    from app.services.jira_service import JiraService
    decrypted = decrypt_credentials(credential.encrypted_data)
    jira_service = JiraService(server=decrypted["server_url"], email=decrypted["email"], api_token=decrypted["api_token"])
    try:
        tickets = await jira_service.execute_query(jql=preview_request.jql_query, max_results=10)
        return JiraPreviewResponse(count=len(tickets), tickets=tickets)
    except Exception as exc:
        logger.error("JQL query preview failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="JQL query failed — check your query syntax and Jira credentials")
