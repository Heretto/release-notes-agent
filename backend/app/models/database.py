"""Database models for the release-notes-agent application.

Core models (User, Organization, Credential, Agent, ...) are provided by hop-core.
This file defines domain-specific models and adds domain relationships to core models.

Domain shape (see docs/COLLABORATIVE_WORKFLOW.md):

    InstructionSet ──< Job ──< JobJiraIssue        (snapshot of every issue the query returned)
                          ──< ReleaseNoteItem     (one user-facing change, written as DITA)
                                 >─< JobJiraIssue  (an issue can feed several notes, and a note
                                                    can come from several issues)
                                 ──< ReleaseNoteItemHistory    (what changed, when, by whom)
                          ──< ReleaseNoteTopic    (the assembled DITA topics)
                          ──< ReleaseNoteChatMessage
"""

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer, ForeignKey, Enum as SQLEnum, ARRAY, JSON,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

# Re-export hop-core models and utilities for backward compatibility
from hop_core.db import Base, get_db, init_db, init_engine, get_engine, get_session_factory
from hop_core.models.user import User
from hop_core.models.organization import Organization, OrganizationMember, OrganizationInvitation, user_organizations
from hop_core.models.credential import Credential
from hop_core.models.enums import OrganizationRole, CredentialTypeRegistry
from hop_core.models.agent import Agent
from hop_core.credentials.builtin import register_builtin_types

# Legacy CredentialType enum — used by existing code that references CredentialType.JIRA, etc.
# New code should use string types via CredentialTypeRegistry instead.
class CredentialType(str, enum.Enum):
    JIRA = "jira"
    HERETTO = "heretto"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

# Every credential type this app uses is a hop-core built-in, so register them from there
# rather than by hand. One call brings the field specs the generic credentials UI renders
# forms from, the connection testers behind the Test button, and — for the AI providers —
# the AiProviderRegistry generators AgentRunner needs. Registering the types bare, as this
# used to, left the UI with no fields to render and the testers unregistered.
register_builtin_types("jira", "heretto", "anthropic", "openai", "gemini")

# Domain enums
class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobTrigger(str, enum.Enum):
    MANUAL = "manual"
    WEBHOOK = "webhook"
    SCHEDULED = "scheduled"


# Plain string "enums": kept as constants rather than SQLEnum so adding a value never needs
# a migration.

class JobStage:
    """Where a running job is in the pipeline. Stored on Job.stage."""
    FETCH_ISSUES = "fetch_issues"
    EVALUATE = "evaluate"
    CONSOLIDATE = "consolidate"
    ORGANIZE = "organize"
    WRITE = "write"
    ASSEMBLE = "assemble"
    PUBLISH = "publish"
    DONE = "done"
    ORDER = [FETCH_ISSUES, EVALUATE, CONSOLIDATE, ORGANIZE, WRITE, ASSEMBLE, PUBLISH, DONE]


class ItemStatus:
    """Review status a person sets on a release note item."""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"   # excluded from the assembled topics
    ALL = (DRAFT, REVIEW, APPROVED, REJECTED)


class ChunkingStrategy:
    """How release note items are split into DITA topics."""
    SINGLE = "single"             # every note in one topic (the default)
    BY_GROUP = "by_group"         # one topic per organization group
    BY_COMPONENT = "by_component" # one topic per Jira component
    ALL = (SINGLE, BY_GROUP, BY_COMPONENT)


class IssueRelevance:
    PENDING = "pending"
    RELEVANT = "relevant"
    NOT_RELEVANT = "not_relevant"


class HistoryEvent:
    CREATED = "created"
    JIRA_CHANGED = "jira_changed"
    REGENERATED = "regenerated"
    CONTENT_EDITED = "content_edited"
    STATUS_CHANGED = "status_changed"
    MOVED = "moved"
    FLAGGED = "flagged"
    ISSUE_REMOVED = "issue_removed"
    NOTES_EDITED = "notes_edited"


# --- Domain models ---

class InstructionSet(Base):
    __tablename__ = "instruction_sets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    jql_query = Column(Text, nullable=False)
    jira_credential_id = Column(UUID(as_uuid=True), ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True)
    dita_template_id = Column(UUID(as_uuid=True), ForeignKey("dita_templates.id"))
    heretto_folder_id = Column(String(255))
    publish_to_heretto = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)

    # Agents by role. The writer writes every note's DITA and is the agent a person chats
    # with in the workspace; the analysis agent evaluates issues and organizes notes and
    # falls back to the writer when unset. SET NULL: deleting an agent must leave the
    # instruction set visibly unconfigured, not delete it.
    writer_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    analysis_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)

    # Pipeline configuration
    product_name = Column(String(255), nullable=True)
    relevance_guidance = Column(Text, nullable=True)      # what counts as a change users must know about
    organization_guidance = Column(Text, nullable=True)   # how to group and order the notes
    chunking_strategy = Column(String(40), nullable=False, default=ChunkingStrategy.SINGLE, server_default=ChunkingStrategy.SINGLE)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    jira_credential = relationship("Credential", foreign_keys=[jira_credential_id])
    dita_template = relationship("DitaTemplate")
    writer_agent = relationship("Agent", foreign_keys=[writer_agent_id])
    analysis_agent = relationship("Agent", foreign_keys=[analysis_agent_id])
    jobs = relationship("Job", back_populates="instruction_set")


class Job(Base):
    """A release: one run of the pipeline plus everything a person does with the result."""
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    instruction_set_id = Column(UUID(as_uuid=True), ForeignKey("instruction_sets.id"))
    title = Column(String(255), nullable=True)
    jql_query = Column(Text, nullable=False)
    status = Column(SQLEnum(JobStatus), nullable=False, default=JobStatus.PENDING)
    triggered_by = Column(SQLEnum(JobTrigger), nullable=False)
    output_filename = Column(String(255))
    heretto_folder_id = Column(String(255))
    auto_publish = Column(Boolean, default=False)
    tickets_processed = Column(Integer, default=0)
    max_tickets = Column(Integer, nullable=True)
    error_message = Column(Text)

    # Pipeline progress and the state the workspace builds on
    stage = Column(String(40), nullable=True)
    stage_message = Column(Text, nullable=True)
    chunking_strategy = Column(String(40), nullable=False, default=ChunkingStrategy.SINGLE, server_default=ChunkingStrategy.SINGLE)
    run_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_run_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    instruction_set = relationship("InstructionSet", back_populates="jobs")
    artifacts = relationship("JobArtifact", back_populates="job", cascade="all, delete-orphan")
    requests = relationship("JobRequest", back_populates="job", cascade="all, delete-orphan")
    issues = relationship("JobJiraIssue", back_populates="job", cascade="all, delete-orphan", order_by="JobJiraIssue.issue_key")
    items = relationship("ReleaseNoteItem", back_populates="job", cascade="all, delete-orphan", order_by="ReleaseNoteItem.position")
    topics = relationship("ReleaseNoteTopic", back_populates="job", cascade="all, delete-orphan", order_by="ReleaseNoteTopic.position")
    chat_messages = relationship("ReleaseNoteChatMessage", back_populates="job", cascade="all, delete-orphan", order_by="ReleaseNoteChatMessage.created_at")


class JobJiraIssue(Base):
    """A snapshot of one Jira issue as the job last saw it.

    ``content_hash`` covers the fields a release note can depend on, so a rerun can tell
    "nothing changed" from "the ticket moved" without a field-by-field comparison.
    """
    __tablename__ = "job_jira_issues"
    __table_args__ = (UniqueConstraint("job_id", "issue_key", name="uq_job_jira_issues_job_key"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_key = Column(String(64), nullable=False)
    url = Column(Text, nullable=True)
    summary = Column(Text, nullable=False, default="")
    description = Column(Text, nullable=True)
    issue_type = Column(String(100), nullable=True)
    status = Column(String(100), nullable=True)
    priority = Column(String(100), nullable=True)
    labels = Column(JSON, nullable=False, default=list)
    components = Column(JSON, nullable=False, default=list)
    fix_versions = Column(JSON, nullable=False, default=list)
    comments = Column(JSON, nullable=False, default=list)
    assignee = Column(String(255), nullable=True)
    reporter = Column(String(255), nullable=True)
    jira_created = Column(String(64), nullable=True)
    jira_updated = Column(String(64), nullable=True)
    content_hash = Column(String(64), nullable=False)

    relevance = Column(String(20), nullable=False, default=IssueRelevance.PENDING, server_default=IssueRelevance.PENDING)
    relevance_reason = Column(Text, nullable=True)
    # False once a rerun's query no longer returns the issue. Kept so its notes keep their source.
    in_query = Column(Boolean, nullable=False, default=True, server_default="true")

    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    changed_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("Job", back_populates="issues")
    item_links = relationship("ReleaseNoteItemIssue", back_populates="issue", cascade="all, delete-orphan")


class ReleaseNoteItem(Base):
    """One change end users need to know about, written as a DITA fragment."""
    __tablename__ = "release_note_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("release_note_topics.id", ondelete="SET NULL"), nullable=True)
    position = Column(Integer, nullable=False, default=0)
    group_name = Column(String(255), nullable=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=False, default="")
    # A <div outputclass="release-note"> body fragment; see topic_assembler.
    dita_content = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default=ItemStatus.DRAFT, server_default=ItemStatus.DRAFT)
    # Set when something happened the person should look at (its Jira issue changed after a
    # person edited it, or dropped out of the query). Cleared by the person.
    needs_attention = Column(Boolean, nullable=False, default=False, server_default="false")
    attention_reason = Column(Text, nullable=True)
    # True once a person has edited the content; a rerun then flags instead of rewriting.
    user_edited = Column(Boolean, nullable=False, default=False, server_default="false")
    # Free text a person keeps alongside the note: context, open questions, links to a Slack
    # thread or design doc. Replaced the structured references table; URLs in it are linked
    # when rendered. Never shown to readers — it does not reach the assembled topic.
    notes = Column(Text, nullable=False, default="", server_default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    job = relationship("Job", back_populates="items")
    topic = relationship("ReleaseNoteTopic", back_populates="items")
    issue_links = relationship("ReleaseNoteItemIssue", back_populates="item", cascade="all, delete-orphan")
    history = relationship("ReleaseNoteItemHistory", back_populates="item", cascade="all, delete-orphan", order_by="ReleaseNoteItemHistory.created_at.desc()")

    @property
    def issues(self):
        return [link.issue for link in self.issue_links]

    @property
    def fragment_id(self) -> str:
        """The id attribute of this note's <div> in the assembled topic."""
        return f"rn-{str(self.id).split('-')[0]}"


class ReleaseNoteItemIssue(Base):
    __tablename__ = "release_note_item_issues"
    __table_args__ = (UniqueConstraint("item_id", "issue_id", name="uq_release_note_item_issue"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("release_note_items.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_id = Column(UUID(as_uuid=True), ForeignKey("job_jira_issues.id", ondelete="CASCADE"), nullable=False, index=True)

    item = relationship("ReleaseNoteItem", back_populates="issue_links")
    issue = relationship("JobJiraIssue", back_populates="item_links")


class ReleaseNoteItemHistory(Base):
    """What happened to a note: created, its Jira issue changed, edited, status set, ..."""
    __tablename__ = "release_note_item_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("release_note_items.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(40), nullable=False)
    # "system" (the pipeline), "agent" (a chat edit), or "user"
    actor = Column(String(20), nullable=False, default="system")
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    summary = Column(Text, nullable=False)
    # Structured detail: field diffs, previous content, the issue key involved, ...
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("ReleaseNoteItem", back_populates="history")
    user = relationship("User", foreign_keys=[user_id])


class ReleaseNoteTopic(Base):
    """An assembled DITA topic holding some or all of a job's notes."""
    __tablename__ = "release_note_topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False, default=0)
    slug = Column(String(255), nullable=False)       # the topic's id attribute
    title = Column(String(500), nullable=False)
    filename = Column(String(255), nullable=False)
    dita_content = Column(Text, nullable=False, default="")
    heretto_doc_id = Column(String(255), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    job = relationship("Job", back_populates="topics")
    items = relationship("ReleaseNoteItem", back_populates="topic", order_by="ReleaseNoteItem.position")


class ReleaseNoteChatMessage(Base):
    __tablename__ = "release_note_chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    role = Column(String(20), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    # The tool calls the agent made while answering: [{tool, args, result}]
    actions = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="chat_messages")
    user = relationship("User", foreign_keys=[user_id])


class JobArtifact(Base):
    __tablename__ = "job_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    artifact_type = Column(String(50), nullable=False)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    heretto_doc_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="artifacts")

class JobRequest(Base):
    __tablename__ = "job_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    request_type = Column(String(50), nullable=False)
    request_data = Column(Text, nullable=True)
    response_data = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="requests")

class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    trigger_events = Column(ARRAY(Text), nullable=False)
    jql_filter = Column(Text)
    instruction_set_id = Column(UUID(as_uuid=True), ForeignKey("instruction_sets.id"), nullable=False)
    auto_publish = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    secret_token = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    instruction_set = relationship("InstructionSet")

class DitaTemplate(Base):
    __tablename__ = "dita_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    template_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])


# --- Add domain relationships to core models ---
# These are added after class definition (SQLAlchemy supports this).

User.instruction_sets = relationship("InstructionSet", foreign_keys="InstructionSet.user_id", cascade="all, delete-orphan")
User.jobs = relationship("Job", foreign_keys="Job.user_id", cascade="all, delete-orphan")
User.webhook_configs = relationship("WebhookConfig", foreign_keys="WebhookConfig.user_id", cascade="all, delete-orphan")
User.dita_templates = relationship("DitaTemplate", foreign_keys="DitaTemplate.user_id", cascade="all, delete-orphan")

Organization.instruction_sets = relationship("InstructionSet", foreign_keys="InstructionSet.organization_id", cascade="all, delete-orphan")
Organization.jobs = relationship("Job", foreign_keys="Job.organization_id", cascade="all, delete-orphan")


# --- Backward-compatible engine/session (lazy, initialized by hop-core) ---

class _SessionLocalProxy:
    """Proxy that lazily returns sessions from hop-core's session factory."""
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)

SessionLocal = _SessionLocalProxy()
