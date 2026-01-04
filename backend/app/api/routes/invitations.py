"""Invitation acceptance routes for unauthenticated users."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
from uuid import UUID

from app.models.database import get_db, User
from app.models.organization import Organization, OrganizationMember, OrganizationInvitation
from app.core.security import get_password_hash
from app.models.schemas import OrganizationInvitationResponse

router = APIRouter(prefix="/invitations")


class InvitationInfoResponse(BaseModel):
    """Response model for invitation information."""
    email: str
    organization_name: str
    role: str
    invited_by_email: str
    expires_at: datetime
    is_existing_user: bool


class AcceptInvitationRequest(BaseModel):
    """Request model for accepting an invitation."""
    password: str
    confirm_password: str


class AcceptInvitationResponse(BaseModel):
    """Response model for successful invitation acceptance."""
    message: str
    email: str
    organization_name: str


@router.get("/info/{token}", response_model=InvitationInfoResponse)
async def get_invitation_info(
    token: str,
    db: Session = Depends(get_db)
):
    """Get information about an invitation (public endpoint)."""
    invitation = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token == token,
        OrganizationInvitation.accepted_at.is_(None)
    ).first()
    
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invitation"
        )
    
    # Check if invitation has expired
    if invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired"
        )
    
    # Get organization info
    organization = db.query(Organization).filter(
        Organization.id == invitation.organization_id
    ).first()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Get inviter info
    inviter = db.query(User).filter(
        User.id == invitation.invited_by
    ).first()
    
    # Check if user already exists
    existing_user = db.query(User).filter(
        User.email == invitation.email
    ).first()
    
    return InvitationInfoResponse(
        email=invitation.email,
        organization_name=organization.name,
        role=invitation.role.value if hasattr(invitation.role, 'value') else invitation.role,
        invited_by_email=inviter.email if inviter else "Unknown",
        expires_at=invitation.expires_at,
        is_existing_user=existing_user is not None
    )


@router.post("/accept/{token}", response_model=AcceptInvitationResponse)
async def accept_invitation_new_user(
    token: str,
    request: AcceptInvitationRequest,
    db: Session = Depends(get_db)
):
    """Accept an invitation and create account if new user (public endpoint)."""
    # Validate passwords match
    if request.password != request.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
    
    # Validate password strength
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Get invitation
    invitation = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token == token,
        OrganizationInvitation.accepted_at.is_(None)
    ).first()
    
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invitation"
        )
    
    # Check if invitation has expired
    if invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired"
        )
    
    # Get organization
    organization = db.query(Organization).filter(
        Organization.id == invitation.organization_id
    ).first()
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Check if user exists
    user = db.query(User).filter(
        User.email == invitation.email
    ).first()
    
    if not user:
        # Create new user
        user = User(
            email=invitation.email,
            password_hash=get_password_hash(request.password),
            is_active=True,
            is_superuser=False
        )
        db.add(user)
        db.flush()
    else:
        # For existing users, update password if they're accepting invitation
        # This allows password reset via invitation
        user.password_hash = get_password_hash(request.password)
    
    # Check if already a member
    existing_member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id,
        OrganizationMember.organization_id == invitation.organization_id
    ).first()
    
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization"
        )
    
    # Add user to organization
    member = OrganizationMember(
        organization_id=invitation.organization_id,
        user_id=user.id,
        role=invitation.role,
        invited_by=invitation.invited_by,
        joined_at=datetime.now(timezone.utc)
    )
    db.add(member)
    
    # Mark invitation as accepted
    invitation.accepted_at = datetime.now(timezone.utc)
    invitation.accepted_by = user.id
    
    # Commit all changes
    db.commit()
    
    return AcceptInvitationResponse(
        message="Invitation accepted successfully. You can now log in with your email and password.",
        email=user.email,
        organization_name=organization.name
    )


class ExistingUserAcceptRequest(BaseModel):
    """Request model for existing users accepting invitations."""
    password: str


@router.post("/accept-existing/{token}")
async def accept_invitation_existing_user(
    token: str,
    request: ExistingUserAcceptRequest,
    db: Session = Depends(get_db)
):
    """Accept invitation for existing users (requires password verification)."""
    from app.core.security import verify_password
    
    # Get invitation
    invitation = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token == token,
        OrganizationInvitation.accepted_at.is_(None)
    ).first()
    
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invitation"
        )
    
    # Check if invitation has expired
    if invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired"
        )
    
    # Get user
    user = db.query(User).filter(
        User.email == invitation.email
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please use the new user registration flow"
        )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    # Check if already a member
    existing_member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id,
        OrganizationMember.organization_id == invitation.organization_id
    ).first()
    
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this organization"
        )
    
    # Add user to organization
    member = OrganizationMember(
        organization_id=invitation.organization_id,
        user_id=user.id,
        role=invitation.role,
        invited_by=invitation.invited_by,
        joined_at=datetime.now(timezone.utc)
    )
    db.add(member)
    
    # Mark invitation as accepted
    invitation.accepted_at = datetime.now(timezone.utc)
    invitation.accepted_by = user.id
    
    db.commit()
    
    # Get organization
    organization = db.query(Organization).filter(
        Organization.id == invitation.organization_id
    ).first()
    
    return AcceptInvitationResponse(
        message="Invitation accepted successfully. You have been added to the organization.",
        email=user.email,
        organization_name=organization.name if organization else "Unknown"
    )