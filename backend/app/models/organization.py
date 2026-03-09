"""Organization model and related schemas for multi-tenancy support."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

# Import the models from database.py to avoid duplication
from app.models.database import Organization, OrganizationRole, OrganizationMember, user_organizations, OrganizationInvitation

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

class OrganizationMemberSchema(BaseModel):
    user_id: str
    email: str
    role: OrganizationRole
    joined_at: datetime