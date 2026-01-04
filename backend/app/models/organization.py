"""Organization models for multi-tenancy support."""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum as SQLEnum, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.models.database import Base


class OrganizationRole(str, enum.Enum):
    """Roles within an organization."""
    ADMIN = "admin"
    MEMBER = "member"


class Organization(Base):
    """Organization model for multi-tenancy."""
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    settings = Column(JSON, default={})  # For org-specific configurations
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    credentials = relationship("Credential", back_populates="organization", cascade="all, delete-orphan")
    instruction_sets = relationship("InstructionSet", back_populates="organization", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="organization", cascade="all, delete-orphan")
    webhook_configs = relationship("WebhookConfig", back_populates="organization", cascade="all, delete-orphan")
    dita_templates = relationship("DitaTemplate", back_populates="organization", cascade="all, delete-orphan")


class OrganizationMember(Base):
    """Organization membership model."""
    __tablename__ = "organization_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(SQLEnum(OrganizationRole), nullable=False, default=OrganizationRole.MEMBER)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Ensure unique membership
    __table_args__ = (
        UniqueConstraint('organization_id', 'user_id', name='unique_org_member'),
    )
    
    # Relationships
    organization = relationship("Organization", back_populates="members")
    user = relationship("User", foreign_keys=[user_id], back_populates="organization_memberships")
    inviter = relationship("User", foreign_keys=[invited_by])


class OrganizationInvitation(Base):
    """Pending organization invitations."""
    __tablename__ = "organization_invitations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(SQLEnum(OrganizationRole), nullable=False, default=OrganizationRole.MEMBER)
    token = Column(String(255), unique=True, nullable=False, index=True)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    organization = relationship("Organization")
    inviter = relationship("User", foreign_keys=[invited_by])
    accepter = relationship("User", foreign_keys=[accepted_by])