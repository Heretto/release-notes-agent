"""Superuser administration endpoints for managing all organizations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, select
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

from pydantic import EmailStr
from datetime import timedelta, timezone
import secrets

from app.models.database import (
    get_db, User, Organization, Job, OrganizationInvitation, user_organizations
)
from app.core.security import get_password_hash
from app.api.dependencies import get_current_superuser

router = APIRouter(prefix="/superadmin")


# Response schemas
class SuperadminOrgListItem(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    member_count: int
    created_by_email: Optional[str] = None
    last_activity: Optional[datetime] = None

    class Config:
        from_attributes = True


class SuperadminOrgMember(BaseModel):
    user_id: UUID
    email: str
    role: str
    is_active: bool
    joined_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SuperadminOrgDetail(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    member_count: int
    job_count: int
    created_by_email: Optional[str] = None
    last_activity: Optional[datetime] = None
    members: List[SuperadminOrgMember] = []

    class Config:
        from_attributes = True


@router.get("/organizations", response_model=List[SuperadminOrgListItem])
async def list_all_organizations(
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """List all organizations with stats (superuser only)."""
    orgs = db.query(Organization).order_by(desc(Organization.created_at)).all()

    results = []
    for org in orgs:
        # Count members via user_organizations table
        member_count = db.execute(
            select(func.count()).select_from(user_organizations).where(
                user_organizations.c.organization_id == org.id
            )
        ).scalar() or 0

        # Find the first member (creator) of the organization
        first_member = db.execute(
            select(user_organizations).where(
                user_organizations.c.organization_id == org.id
            ).order_by(user_organizations.c.joined_at.asc())
        ).first()

        created_by_email = None
        if first_member:
            creator = db.query(User).filter(User.id == first_member.user_id).first()
            if creator:
                created_by_email = creator.email

        # Last activity = most recent job created_at for this org
        last_job = db.query(Job.created_at).filter(
            Job.organization_id == org.id
        ).order_by(desc(Job.created_at)).first()

        last_activity = last_job[0] if last_job else None

        results.append(SuperadminOrgListItem(
            id=org.id,
            name=org.name,
            slug=org.slug,
            is_active=org.is_active,
            created_at=org.created_at,
            member_count=member_count,
            created_by_email=created_by_email,
            last_activity=last_activity,
        ))

    return results


@router.get("/organizations/{org_id}", response_model=SuperadminOrgDetail)
async def get_organization_detail(
    org_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Get detailed organization info with members (superuser only)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Get memberships from user_organizations table
    memberships = db.execute(
        select(user_organizations).where(
            user_organizations.c.organization_id == org.id
        )
    ).all()

    members = []
    for m in memberships:
        user = db.query(User).filter(User.id == m.user_id).first()
        if user:
            members.append(SuperadminOrgMember(
                user_id=user.id,
                email=user.email,
                role=m.role or 'member',
                is_active=user.is_active,
                joined_at=m.joined_at,
            ))

    job_count = db.query(func.count(Job.id)).filter(
        Job.organization_id == org.id
    ).scalar() or 0

    # Find creator (first member)
    first_member = db.execute(
        select(user_organizations).where(
            user_organizations.c.organization_id == org.id
        ).order_by(user_organizations.c.joined_at.asc())
    ).first()

    created_by_email = None
    if first_member:
        creator = db.query(User).filter(User.id == first_member.user_id).first()
        if creator:
            created_by_email = creator.email

    # Last activity
    last_job = db.query(Job.created_at).filter(
        Job.organization_id == org.id
    ).order_by(desc(Job.created_at)).first()

    last_activity = last_job[0] if last_job else None

    return SuperadminOrgDetail(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_active=org.is_active,
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=len(members),
        job_count=job_count,
        created_by_email=created_by_email,
        last_activity=last_activity,
        members=members,
    )


@router.delete("/organizations/{org_id}")
async def delete_organization(
    org_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Delete an organization and clean up references (superuser only)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Clear current_organization_id for users pointing to this org
    db.query(User).filter(
        User.current_organization_id == org.id
    ).update({User.current_organization_id: None})

    # Delete the organization (cascades handle members, jobs, credentials, etc.)
    db.delete(org)
    db.commit()

    return {"message": f"Organization '{org.name}' deleted successfully"}


# --- Member management ---

class AddMemberRequest(BaseModel):
    email: EmailStr
    role: str = "member"


@router.post("/organizations/{org_id}/members")
async def add_existing_user_to_org(
    org_id: UUID,
    request: AddMemberRequest,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Add an existing user to an organization (superuser only)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"No user found with email '{request.email}'")

    # Check if already a member
    existing = db.execute(
        select(user_organizations).where(
            user_organizations.c.user_id == user.id,
            user_organizations.c.organization_id == org.id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member of this organization")

    db.execute(
        user_organizations.insert().values(
            user_id=user.id,
            organization_id=org.id,
            role=request.role,
        )
    )

    # Set as current org if user doesn't have one
    if not user.current_organization_id:
        user.current_organization_id = org.id

    db.commit()
    return {"message": f"User '{request.email}' added to '{org.name}' as {request.role}"}


@router.delete("/organizations/{org_id}/members/{user_id}")
async def remove_member_from_org(
    org_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Remove a user from an organization (superuser only)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    existing = db.execute(
        select(user_organizations).where(
            user_organizations.c.user_id == user_id,
            user_organizations.c.organization_id == org_id,
        )
    ).first()
    if not existing:
        raise HTTPException(status_code=404, detail="User is not a member of this organization")

    db.execute(
        user_organizations.delete().where(
            user_organizations.c.user_id == user_id,
            user_organizations.c.organization_id == org_id,
        )
    )

    # Clear current_organization_id if it pointed to this org
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.current_organization_id == org_id:
        user.current_organization_id = None

    db.commit()
    return {"message": "User removed from organization"}


# --- Invitation ---

class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class SuperadminInvitationResponse(BaseModel):
    id: UUID
    email: str
    role: str
    token: str
    expires_at: datetime

    class Config:
        from_attributes = True


@router.post("/organizations/{org_id}/invitations", response_model=SuperadminInvitationResponse)
async def invite_user_to_org(
    org_id: UUID,
    request: InviteUserRequest,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Invite a new user to an organization (superuser only)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if user already exists and is a member
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        existing_member = db.execute(
            select(user_organizations).where(
                user_organizations.c.user_id == existing_user.id,
                user_organizations.c.organization_id == org_id,
            )
        ).first()
        if existing_member:
            raise HTTPException(status_code=400, detail="User is already a member of this organization")

    # Check for pending invitation
    existing_invite = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.email == request.email,
        OrganizationInvitation.organization_id == org_id,
        OrganizationInvitation.accepted_at.is_(None),
    ).first()
    if existing_invite:
        raise HTTPException(status_code=400, detail="An invitation has already been sent to this email")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    invitation = OrganizationInvitation(
        organization_id=org_id,
        email=request.email,
        role=request.role,
        token=token,
        invited_by=current_user.id,
        expires_at=expires_at,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    return SuperadminInvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        token=invitation.token,
        expires_at=invitation.expires_at,
    )
