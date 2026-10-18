"""What the pipeline, the chat agent and the API share about a job's notes and topics.

History recording, position bookkeeping, topic assembly, content edits with validation,
publishing to Heretto, and the response shapes — one place, so a change made by the agent in
chat and the same change made by a person in the UI go through identical code.
"""

from __future__ import annotations

import json
import dataclasses
import logging
from dataclasses import dataclass
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from hop_core.dita import DitaValidator

from app.config import get_settings
from app.core.security import decrypt_credentials
from app.models.database import (
    ChunkingStrategy, Credential, CredentialType, HistoryEvent, IssueRelevance, ItemStatus, Job,
    JobArtifact, JobJiraIssue, JobRequest, ReleaseNoteItem, ReleaseNoteItemHistory,
    ReleaseNoteTopic,
)
from app.models.schemas import (
    ChatMessageResponse, ItemCommentResponse, ItemHistoryResponse, JobCounts, JobIssueResponse,
    JobResponse, ReleaseNoteItemDetailResponse, ReleaseNoteItemResponse, ReleaseNoteTopicResponse,
    HerettoUploadResult,
)
from app.services.heretto_service import HerettoService
from app.services.topic_assembler import (
    FragmentError, Layout, build_topic_xml, coerce_fragment, included_items, plan_topics,
    render_topic_html, validate_topic,
)

logger = logging.getLogger(__name__)


class PublishError(Exception):
    """Publishing could not start; the message is safe to show a person."""


# ── History ──────────────────────────────────────────────────────────────────────────

def record_history(
    db: Session,
    item: ReleaseNoteItem,
    event_type: str,
    summary: str,
    *,
    actor: str = "system",
    user_id: Optional[UUID] = None,
    details: Optional[Dict[str, Any]] = None,
) -> ReleaseNoteItemHistory:
    entry = ReleaseNoteItemHistory(
        item_id=item.id, event_type=event_type, actor=actor, user_id=user_id,
        summary=summary, details=details,
    )
    db.add(entry)
    item.history.append(entry)
    return entry


# ── Naming ───────────────────────────────────────────────────────────────────────────

def extract_version(jql: str) -> Optional[str]:
    """A fixVersion or version named in the JQL, if there is one."""
    for pattern in (r"fixVersion\s*(?:=|in)\s*\(?\s*['\"]([^'\"]+)['\"]", r"\bversion\s*=\s*['\"]([^'\"]+)['\"]"):
        match = re.search(pattern, jql or "", re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def product_name(job: Job) -> str:
    instruction_set = job.instruction_set
    name = (instruction_set.product_name if instruction_set else None) or ""
    return name.strip() or "Product"


def release_title(job: Job) -> str:
    if job.title and job.title.strip():
        return job.title.strip()
    version = extract_version(job.jql_query)
    if version:
        return f"{product_name(job)} {version} release notes"
    when = (job.created_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    return f"{product_name(job)} release notes ({when})"


# ── Ordering ─────────────────────────────────────────────────────────────────────────

def group_order(job: Job) -> List[str]:
    """Group names in the order they first appear by position (ungrouped excluded)."""
    seen: List[str] = []
    for item in sorted(job.items, key=lambda i: i.position):
        name = (item.group_name or "").strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def renumber_positions(job: Job, groups_in_order: Optional[Sequence[str]] = None) -> None:
    """Give every note a dense position: group by group, keeping order inside each group."""
    order = list(groups_in_order) if groups_in_order is not None else group_order(job)
    rank = {name: index for index, name in enumerate(order)}
    items = sorted(
        job.items,
        key=lambda i: (rank.get((i.group_name or "").strip(), len(order) if (i.group_name or "").strip() else len(order) + 1), i.position),
    )
    for index, item in enumerate(items):
        item.position = index


# ── Assembly ─────────────────────────────────────────────────────────────────────────

def assemble_job_topics(
    db: Session,
    job: Job,
    strategy: Optional[str] = None,
    validator: Optional[DitaValidator] = None,
) -> List[ReleaseNoteTopic]:
    """(Re)build the job's topics from its notes with the given chunking strategy.

    Topics are matched by slug so a republished topic keeps its Heretto document id. One
    download artifact per topic is kept alongside for the plain artifact endpoints.
    Raises FragmentError if an assembled topic does not validate (it should never: every
    fragment was validated on the way in).
    """
    validator = validator or DitaValidator()
    strategy = strategy or job.chunking_strategy or ChunkingStrategy.SINGLE
    if strategy not in ChunkingStrategy.ALL:
        raise ValueError(f"Unknown chunking strategy: {strategy}")
    job.chunking_strategy = strategy

    plans = plan_topics(job.items, strategy, release_title(job), job.output_filename)
    existing = {topic.slug: topic for topic in job.topics}
    kept: List[ReleaseNoteTopic] = []

    layout = Layout.of(job.instruction_set)
    if layout.mode == "agent":
        # Settled by the run; see Job.topic_template.
        layout = dataclasses.replace(layout, template=job.topic_template or "")
    for position, plan in enumerate(plans):
        xml = build_topic_xml(plan, layout=layout)
        errors = validate_topic(xml, validator)
        if errors:
            raise FragmentError(f"Assembled topic '{plan.title}' is not valid DITA", errors)
        topic = existing.pop(plan.slug, None)
        if topic is None:
            topic = ReleaseNoteTopic(job_id=job.id, slug=plan.slug)
            db.add(topic)
            job.topics.append(topic)
        topic.position = position
        topic.title = plan.title
        topic.filename = plan.filename
        topic.dita_content = xml
        kept.append(topic)
        for item in plan.items:
            item.topic = topic

    for stale in existing.values():
        for item in list(stale.items):
            item.topic = None
        job.topics.remove(stale)
        db.delete(stale)

    for item in job.items:
        if item.status == ItemStatus.REJECTED:
            item.topic = None

    # Download artifacts mirror the topics.
    for artifact in [a for a in job.artifacts if a.artifact_type == "dita"]:
        job.artifacts.remove(artifact)
        db.delete(artifact)
    for topic in kept:
        job.artifacts.append(JobArtifact(
            job_id=job.id, artifact_type="dita", filename=topic.filename,
            content=topic.dita_content, heretto_doc_id=topic.heretto_doc_id,
        ))
    db.flush()
    return kept


# ── Edits ────────────────────────────────────────────────────────────────────────────

def set_item_content(
    db: Session,
    item: ReleaseNoteItem,
    dita_content: str,
    *,
    actor: str,
    user_id: Optional[UUID] = None,
    validator: Optional[DitaValidator] = None,
    summary: Optional[str] = None,
) -> bool:
    """Replace a note's fragment after validating it. Returns False when nothing changed."""
    fragment = coerce_fragment(dita_content, item.fragment_id, item.title, validator)
    if fragment.strip() == (item.dita_content or "").strip():
        return False
    previous = item.dita_content
    item.dita_content = fragment
    if actor == "user":
        item.user_edited = True
    record_history(
        db, item, HistoryEvent.CONTENT_EDITED,
        summary or ("Content edited" if actor == "user" else "Content rewritten by the agent"),
        actor=actor, user_id=user_id, details={"previous_dita": previous},
    )
    return True


# ── Credentials ──────────────────────────────────────────────────────────────────────

def find_decryptable_credential(db: Session, user_id: UUID, organization_id: Optional[UUID], cred_type) -> Tuple[Optional[Credential], Optional[dict]]:
    """The first credential of the type(s) the job's user or organization owns that decrypts."""
    query = db.query(Credential).filter(
        or_(Credential.user_id == user_id, Credential.organization_id == organization_id)
    )
    if isinstance(cred_type, (list, tuple)):
        query = query.filter(Credential.type.in_(list(cred_type)))
    else:
        query = query.filter(Credential.type == cred_type)
    for cred in query.all():
        try:
            return cred, decrypt_credentials(cred.encrypted_data)
        except Exception:
            logger.warning("Credential '%s' (id=%s) has stale encryption, skipping", cred.name, cred.id)
    return None, None


# ── Publishing ───────────────────────────────────────────────────────────────────────

def _heretto_credential(db: Session, job: Job, credential_id: Optional[UUID]):
    """The Heretto this release publishes to, and its decrypted settings.

    A folder id is only meaningful in one Heretto, so the connection the folder was chosen
    from is used when it is known. Falling back to "the organization's first Heretto
    credential that decrypts" is for instruction sets saved before the connection was
    recorded; with several connections that fallback is a guess, which is the reason the
    connection is now stored.
    """
    chosen = credential_id or (
        job.instruction_set.heretto_credential_id if job.instruction_set else None)
    if chosen:
        credential = db.query(Credential).filter(
            Credential.id == chosen,
            Credential.organization_id == job.organization_id,
            Credential.type == CredentialType.HERETTO,
        ).first()
        if credential is None:
            raise PublishError(
                "The Heretto connection this folder belongs to is no longer available. "
                "Choose the folder again."
            )
        try:
            return credential, decrypt_credentials(credential.encrypted_data)
        except Exception as exc:  # noqa: BLE001 — a stale key is the operator's to fix
            raise PublishError(
                f"The Heretto connection '{credential.name}' could not be read."
            ) from exc

    return find_decryptable_credential(
        db, job.user_id, job.organization_id, CredentialType.HERETTO)


@dataclass
class PublishOutcome:
    """What a publish did, and where. The folder is what a person wants to open after."""

    results: List[HerettoUploadResult]
    folder_id: Optional[str] = None
    folder_url: Optional[str] = None

    def __iter__(self):
        # Callers that only care what happened can still iterate the outcome.
        return iter(self.results)


async def publish_topics(
    db: Session, job: Job, folder_id: Optional[str] = None,
    credential_id: Optional[UUID] = None,
) -> PublishOutcome:
    """Create or update every topic in Heretto. Raises PublishError when it cannot start.

    `folder_id` publishes this once into somewhere other than the release's usual folder —
    a person choosing a destination in the workspace. It is deliberately not stored: a
    one-off destination that quietly became the default is how notes end up somewhere
    nobody expects on the next run.
    """
    settings = get_settings()
    instruction_set = job.instruction_set
    folder_id = folder_id or job.heretto_folder_id or (
        instruction_set.heretto_folder_id if instruction_set else None)
    if not folder_id:
        raise PublishError("No Heretto folder is configured for this job or its instruction set.")
    heretto_cred, heretto_config = _heretto_credential(db, job, credential_id)
    if not heretto_cred:
        raise PublishError("No Heretto credentials found. Add one in the Credentials page.")

    service = HerettoService(
        base_url=heretto_config.get("server_url", settings.heretto_base_url),
        username=heretto_config["username"],
        token=heretto_config["token"],
    )
    results: List[HerettoUploadResult] = []
    for topic in sorted(job.topics, key=lambda t: t.position):
        request = JobRequest(
            job_id=job.id, request_type="heretto_publish", status="pending",
            request_data=json.dumps({
                "topic": topic.title, "filename": topic.filename, "folder_id": folder_id,
                "document_id": topic.heretto_doc_id, "content_length": len(topic.dita_content or ""),
            }),
        )
        db.add(request)
        db.commit()
        started = time.time()
        try:
            document_id = topic.heretto_doc_id
            if not document_id:
                # A file of this name may already be there — published by an earlier
                # release, or by hand. Update it rather than leaving the folder with two
                # files of the same name and only one of them maintained.
                document_id = await service.find_document(folder_id, topic.filename)
                if document_id:
                    logger.info(
                        "Publishing '%s' over the existing document %s in folder %s",
                        topic.filename, document_id, folder_id,
                    )

            if document_id:
                result = await service.update_dita_topic(document_id, topic.dita_content)
                if not result.success and "HTTP 404" in (result.message or ""):
                    # The document was deleted in Heretto; create it again.
                    result = await service.upload_dita_topic(topic.dita_content, topic.filename, folder_id)
            else:
                result = await service.upload_dita_topic(topic.dita_content, topic.filename, folder_id)
        except Exception as exc:
            logger.error("Publishing topic %s failed: %s", topic.id, exc, exc_info=True)
            result = HerettoUploadResult(success=False, document_id=topic.heretto_doc_id, message="Publishing failed unexpectedly", url=None)

        request.duration_ms = int((time.time() - started) * 1000)
        result.title = topic.title
        if result.success:
            topic.heretto_doc_id = result.document_id
            topic.published_at = datetime.now(timezone.utc)
            for artifact in job.artifacts:
                if artifact.artifact_type == "dita" and artifact.filename == topic.filename:
                    artifact.heretto_doc_id = result.document_id
            request.status = "success"
            request.response_data = json.dumps({"document_id": result.document_id, "message": result.message})
        else:
            request.status = "failed"
            request.error_message = result.message
        db.commit()
        results.append(result)
    return PublishOutcome(
        results=results, folder_id=folder_id, folder_url=service.folder_url(folder_id),
    )


# ── Response shapes ──────────────────────────────────────────────────────────────────

def issue_to_response(issue: JobJiraIssue) -> JobIssueResponse:
    return JobIssueResponse(
        id=issue.id, issue_key=issue.issue_key, url=issue.url, summary=issue.summary or "",
        description=issue.description, issue_type=issue.issue_type, status=issue.status,
        priority=issue.priority, labels=list(issue.labels or []), components=list(issue.components or []),
        fix_versions=list(issue.fix_versions or []), comments=list(issue.comments or []),
        assignee=issue.assignee, reporter=issue.reporter, jira_created=issue.jira_created,
        jira_updated=issue.jira_updated, relevance=issue.relevance, relevance_reason=issue.relevance_reason,
        in_query=bool(issue.in_query), item_ids=[link.item_id for link in issue.item_links],
        changed_at=issue.changed_at,
    )


def _item_fields(item: ReleaseNoteItem) -> dict:
    return dict(
        id=item.id, job_id=item.job_id, topic_id=item.topic_id, fragment_id=item.fragment_id,
        position=item.position, group_name=item.group_name, title=item.title, summary=item.summary or "",
        dita_content=item.dita_content or "", status=item.status, needs_attention=bool(item.needs_attention),
        attention_reason=item.attention_reason, user_edited=bool(item.user_edited),
        issue_keys=[link.issue.issue_key for link in item.issue_links],
        has_notes=bool((item.notes or "").strip()),
        reviewer_id=item.reviewer_id,
        reviewer_email=item.reviewer.email if item.reviewer else None,
        reviewed=bool(item.reviewed), comment_count=len(item.comments),
        approved_by_email=item.approved_by.email if item.approved_by else None,
        approved_at=item.approved_at,
        created_at=item.created_at, updated_at=item.updated_at,
    )


def comment_to_response(comment) -> ItemCommentResponse:
    return ItemCommentResponse(
        id=comment.id, user_id=comment.user_id,
        user_email=comment.user.email if comment.user else None,
        body=comment.body,
        resolved=bool(comment.resolved), resolved_at=comment.resolved_at,
        resolved_by_email=comment.resolved_by.email if comment.resolved_by else None,
        created_at=comment.created_at,
    )


def item_to_response(item: ReleaseNoteItem) -> ReleaseNoteItemResponse:
    return ReleaseNoteItemResponse(**_item_fields(item))


def item_to_detail(item: ReleaseNoteItem) -> ReleaseNoteItemDetailResponse:
    return ReleaseNoteItemDetailResponse(
        **_item_fields(item),
        issues=[issue_to_response(link.issue) for link in item.issue_links],
        notes=item.notes or "",
        comments=[comment_to_response(c) for c in item.comments],
        history=[
            ItemHistoryResponse(
                id=h.id, event_type=h.event_type, actor=h.actor, user_id=h.user_id,
                summary=h.summary, details=h.details, created_at=h.created_at,
            )
            for h in sorted(item.history, key=lambda h: h.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        ],
    )


def topic_to_response(topic: ReleaseNoteTopic, with_html: bool = True) -> ReleaseNoteTopicResponse:
    html, warnings = (None, [])
    if with_html:
        html, warnings = render_topic_html(topic.dita_content or "")
    return ReleaseNoteTopicResponse(
        id=topic.id, position=topic.position, slug=topic.slug, title=topic.title, filename=topic.filename,
        dita_content=topic.dita_content or "", html=html, render_warnings=warnings,
        heretto_doc_id=topic.heretto_doc_id, published_at=topic.published_at,
        item_ids=[i.id for i in sorted(topic.items, key=lambda i: i.position)], updated_at=topic.updated_at,
    )


def chat_message_to_response(message) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id, role=message.role, content=message.content, actions=message.actions,
        user_id=message.user_id, created_at=message.created_at,
    )


def job_counts(job: Job) -> JobCounts:
    items = list(job.items)
    return JobCounts(
        issues=len(job.issues),
        relevant_issues=sum(1 for i in job.issues if i.relevance == IssueRelevance.RELEVANT),
        items=sum(1 for i in items if i.status != ItemStatus.REJECTED),
        approved_items=sum(1 for i in items if i.status == ItemStatus.APPROVED),
        attention_items=sum(1 for i in items if i.needs_attention),
        topics=len(job.topics),
    )


def job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id, user_id=job.user_id, instruction_set_id=job.instruction_set_id,
        instruction_set_name=job.instruction_set.name if job.instruction_set else None,
        title=job.title, jql_query=job.jql_query, variables=job.variables or {},
        uses_instruction_query=bool(getattr(job, "uses_instruction_query", True)),
        auto_publish=bool(job.auto_publish), heretto_folder_id=job.heretto_folder_id,
        status=job.status, triggered_by=job.triggered_by, output_filename=job.output_filename,
        tickets_processed=job.tickets_processed or 0, max_tickets=job.max_tickets,
        error_message=job.error_message, stage=job.stage, stage_message=job.stage_message,
        chunking_strategy=job.chunking_strategy or ChunkingStrategy.SINGLE, run_count=job.run_count or 0,
        last_run_at=job.last_run_at, created_at=job.created_at, started_at=job.started_at,
        completed_at=job.completed_at, counts=job_counts(job),
    )


# ── Moving notes ─────────────────────────────────────────────────────────────────────

def move_item(job: Job, item: ReleaseNoteItem, group_name: Optional[str] = None, position: Optional[int] = None) -> None:
    """Put a note into a group and/or at a 1-based position inside that group.

    Positions across the whole job are renumbered afterwards so the order stays dense.
    """
    order = group_order(job)
    target_group = (group_name if group_name is not None else item.group_name) or ""
    target_group = target_group.strip()
    if target_group and target_group not in order:
        order.append(target_group)
    rank = {name: index for index, name in enumerate(order)}

    def key(i: ReleaseNoteItem):
        name = (i.group_name or "").strip()
        return (rank.get(name, len(order) + 1) if name else len(order), i.position)

    others = sorted((i for i in job.items if i.id != item.id), key=key)
    item.group_name = target_group or None
    group_members = [i for i in others if (i.group_name or "").strip() == target_group]
    if position is None or position < 1:
        index = len(group_members)
    else:
        index = min(position - 1, len(group_members))

    # Rebuild the global order: every other note in place, the moved note inserted into its group.
    ordered: List[ReleaseNoteItem] = []
    inserted = False
    seen_in_group = 0
    for other in others:
        same_group = (other.group_name or "").strip() == target_group
        if same_group and not inserted and seen_in_group == index:
            ordered.append(item)
            inserted = True
        ordered.append(other)
        if same_group:
            seen_in_group += 1
    if not inserted:
        # Append at the end of the group (or at the end of everything for a brand-new group).
        last_index = max((n for n, o in enumerate(ordered) if (o.group_name or "").strip() == target_group), default=None)
        if last_index is None:
            ordered.append(item)
        else:
            ordered.insert(last_index + 1, item)
    for n, note in enumerate(ordered):
        note.position = n
    renumber_positions(job, order)
