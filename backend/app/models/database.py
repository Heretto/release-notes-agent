from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, Integer, ForeignKey, Enum as SQLEnum, ARRAY, LargeBinary, Table, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func
import uuid
import enum
from typing import AsyncGenerator

from app.config import get_settings

settings = get_settings()

# Create base class for models
Base = declarative_base()

# Create engine and session
engine = create_engine(settings.database_url, echo=settings.app_debug)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Enums
class CredentialType(str, enum.Enum):
    JIRA = "jira"
    HERETTO = "heretto"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

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

class OrganizationRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"

# Organization membership model
class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    role = Column(SQLEnum(OrganizationRole, name='organizationrole', create_type=False), nullable=False, default=OrganizationRole.MEMBER)
    invited_by = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="memberships")
    organization = relationship("Organization", foreign_keys=[organization_id], back_populates="members")
    inviter = relationship("User", foreign_keys=[invited_by])

# Backward-compatible alias for the legacy table (still exists but unused for new code)
user_organizations = OrganizationMember.__table__

# Models
class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)  # URL-friendly identifier
    settings = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    members = relationship("OrganizationMember", foreign_keys="OrganizationMember.organization_id", back_populates="organization", cascade="all, delete-orphan")
    credentials = relationship("Credential", back_populates="organization", cascade="all, delete-orphan")
    invitations = relationship("OrganizationInvitation", back_populates="organization", cascade="all, delete-orphan")
    instruction_sets = relationship("InstructionSet", foreign_keys="InstructionSet.organization_id", cascade="all, delete-orphan")
    jobs = relationship("Job", foreign_keys="Job.organization_id", cascade="all, delete-orphan")

class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(50), default="member")
    token = Column(String(255), unique=True, nullable=False)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="invitations")
    inviter = relationship("User", foreign_keys=[invited_by])

# Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Current organization (for quick access to active organization)
    current_organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    
    # Relationships
    memberships = relationship("OrganizationMember", foreign_keys="OrganizationMember.user_id", back_populates="user", cascade="all, delete-orphan")
    current_organization = relationship("Organization", foreign_keys=[current_organization_id])
    credentials = relationship("Credential", back_populates="user", cascade="all, delete-orphan")
    instruction_sets = relationship("InstructionSet", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    webhook_configs = relationship("WebhookConfig", back_populates="user", cascade="all, delete-orphan")
    dita_templates = relationship("DitaTemplate", back_populates="user", cascade="all, delete-orphan")

class Credential(Base):
    __tablename__ = "credentials"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Who created it
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)  # Who owns it
    type = Column(SQLEnum(CredentialType), nullable=False)
    name = Column(String(255), nullable=False)
    encrypted_data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(255), nullable=True)  # Email of creator for display
    
    # Relationships
    user = relationship("User", back_populates="credentials")
    organization = relationship("Organization", back_populates="credentials")

class InstructionSet(Base):
    __tablename__ = "instruction_sets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    jql_query = Column(Text, nullable=False)  # Jira query to execute
    system_prompt = Column(Text, nullable=False)
    user_instructions = Column(Text)
    dita_template_id = Column(UUID(as_uuid=True), ForeignKey("dita_templates.id"))
    heretto_folder_id = Column(String(255))
    publish_to_heretto = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="instruction_sets")
    organization = relationship("Organization", foreign_keys=[organization_id])
    dita_template = relationship("DitaTemplate")
    jobs = relationship("Job", back_populates="instruction_set")

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    instruction_set_id = Column(UUID(as_uuid=True), ForeignKey("instruction_sets.id"))
    ai_credential_id = Column(UUID(as_uuid=True), ForeignKey("credentials.id"), nullable=True)
    jql_query = Column(Text, nullable=False)
    additional_instructions = Column(Text)
    status = Column(SQLEnum(JobStatus), nullable=False, default=JobStatus.PENDING)
    triggered_by = Column(SQLEnum(JobTrigger), nullable=False)
    output_filename = Column(String(255))
    heretto_folder_id = Column(String(255))
    auto_publish = Column(Boolean, default=False)
    tickets_processed = Column(Integer, default=0)
    max_tickets = Column(Integer, nullable=True)  # Maximum number of tickets to process
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="jobs")
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
    
    # Relationships
    job = relationship("Job", back_populates="artifacts")

class JobRequest(Base):
    __tablename__ = "job_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    request_type = Column(String(50), nullable=False)  # 'jira_query', 'ai_generation', 'heretto_publish'
    request_data = Column(Text, nullable=True)  # JSON string of request details
    response_data = Column(Text, nullable=True)  # JSON string of response
    status = Column(String(20), nullable=False, default="pending")  # 'pending', 'success', 'failed'
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
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

    # Relationships
    user = relationship("User", back_populates="webhook_configs")
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
    
    # Relationships
    user = relationship("User", back_populates="dita_templates")

# Database initialization
async def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

async def get_db() -> AsyncGenerator[Session, None]:
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()