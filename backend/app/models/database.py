"""Database models for the release-notes-agent application.

Core models (User, Organization, Credential, etc.) are provided by hop-core.
This file defines domain-specific models and adds domain relationships to core models.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey, Enum as SQLEnum, ARRAY
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

# Legacy CredentialType enum — used by existing code that references CredentialType.JIRA, etc.
# New code should use string types via CredentialTypeRegistry instead.
class CredentialType(str, enum.Enum):
    JIRA = "jira"
    HERETTO = "heretto"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"

# Register credential types with hop-core
CredentialTypeRegistry.register("jira", label="Jira")
CredentialTypeRegistry.register("heretto", label="Heretto")
CredentialTypeRegistry.register("gemini", label="Gemini")
CredentialTypeRegistry.register("openai", label="OpenAI")
CredentialTypeRegistry.register("anthropic", label="Anthropic")
CredentialTypeRegistry.register("azure", label="Azure OpenAI")

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


# --- Domain models ---

class InstructionSet(Base):
    __tablename__ = "instruction_sets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    jql_query = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_instructions = Column(Text)
    dita_template_id = Column(UUID(as_uuid=True), ForeignKey("dita_templates.id"))
    heretto_folder_id = Column(String(255))
    publish_to_heretto = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    dita_template = relationship("DitaTemplate")
    jobs = relationship("Job", back_populates="instruction_set")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    instruction_set_id = Column(UUID(as_uuid=True), ForeignKey("instruction_sets.id"))
    ai_credential_id = Column(UUID(as_uuid=True), ForeignKey("credentials.id", ondelete="SET NULL"), nullable=True)
    jql_query = Column(Text, nullable=False)
    additional_instructions = Column(Text)
    status = Column(SQLEnum(JobStatus), nullable=False, default=JobStatus.PENDING)
    triggered_by = Column(SQLEnum(JobTrigger), nullable=False)
    output_filename = Column(String(255))
    heretto_folder_id = Column(String(255))
    auto_publish = Column(Boolean, default=False)
    tickets_processed = Column(Integer, default=0)
    max_tickets = Column(Integer, nullable=True)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    instruction_set = relationship("InstructionSet", back_populates="jobs")
    ai_credential = relationship("Credential", foreign_keys=[ai_credential_id])
    artifacts = relationship("JobArtifact", back_populates="job", cascade="all, delete-orphan")
    requests = relationship("JobRequest", back_populates="job", cascade="all, delete-orphan")

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
