"""Organization model and related schemas for multi-tenancy support."""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table, UUID as SQLUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import uuid4
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import enum

from app.models.database import Base

# Association table for many-to-many relationship between users and organizations
user_organizations = Table(
    'user_organizations',
    Base.metadata,
    Column('user_id', SQLUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('organization_id', SQLUUID(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), primary_key=True),
    Column('role', String(50), default='member'),  # 'owner', 'admin', 'member'
    Column('joined_at', DateTime(timezone=True), server_default=func.now())
)

class OrganizationRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)  # URL-friendly identifier
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    users = relationship("User", secondary=user_organizations, back_populates="organizations")
    credentials = relationship("Credential", back_populates="organization", cascade="all, delete-orphan")

# Pydantic schemas
class OrganizationCreate(BaseModel):
    name: str
    slug: str

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    member_count: Optional[int] = None

    class Config:
        from_attributes = True

class OrganizationMember(BaseModel):
    user_id: str
    email: str
    role: OrganizationRole
    joined_at: datetime