"""Organization management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone
import secrets
import re

from app.models.database import get_db, User
from app.models.organization import (
    Organization, 
    OrganizationMember, 
    OrganizationRole,
    OrganizationInvitation
)
from app.models.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationMemberCreate,
    OrganizationMemberUpdate,
    OrganizationMemberResponse,
    OrganizationInvitationCreate,
    OrganizationInvitationResponse
)
from app.api.dependencies import (
    get_current_active_user,
    get_current_active_user_with_org,
    require_org_admin,
    CurrentUserContext
)

router = APIRouter(prefix="/organizations")


def create_slug(name: str) -> str:
    """Create a URL-safe slug from a name."""
    # Convert to lowercase and replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower())
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


# Organization endpoints
@router.get("/", response_model=List[OrganizationResponse])
async def list_user_organizations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all organizations the current user belongs to."""
    memberships = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id
    ).all()
    
    organizations = []
    for membership in memberships:
        org = db.query(Organization).filter(
            Organization.id == membership.organization_id
        ).first()
        
        if org:
            # Add member count
            member_count = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == org.id
            ).count()
            
            org_response = OrganizationResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                settings=org.settings or {},
                created_at=org.created_at,
                updated_at=org.updated_at,
                member_count=member_count
            )
            organizations.append(org_response)
    
    return organizations


@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization(
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Get current organization details."""
    org = context.organization
    
    member_count = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id
    ).count()
    
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        settings=org.settings or {},
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=member_count
    )


@router.post("/", response_model=OrganizationResponse)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new organization."""
    # Check if organization name already exists
    existing_org = db.query(Organization).filter(
        Organization.name == org_data.name
    ).first()
    
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name already exists"
        )
    
    # Create slug
    base_slug = create_slug(org_data.name) if not org_data.slug else org_data.slug
    slug = base_slug
    counter = 1
    
    # Ensure unique slug
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Create organization
    new_org = Organization(
        name=org_data.name,
        slug=slug,
        settings=org_data.settings or {}
    )
    
    db.add(new_org)
    db.flush()
    
    # Add creator as admin
    org_member = OrganizationMember(
        organization_id=new_org.id,
        user_id=current_user.id,
        role=OrganizationRole.ADMIN
    )
    
    db.add(org_member)
    db.commit()
    db.refresh(new_org)
    
    return OrganizationResponse(
        id=new_org.id,
        name=new_org.name,
        slug=new_org.slug,
        settings=new_org.settings,
        created_at=new_org.created_at,
        updated_at=new_org.updated_at,
        member_count=1
    )


@router.patch("/current", response_model=OrganizationResponse)
async def update_organization(
    org_data: OrganizationUpdate,
    context: CurrentUserContext = Depends(require_org_admin),
    db: Session = Depends(get_db)
):
    """Update organization details (admin only)."""
    org = context.organization
    
    if org_data.name:
        # Check if new name already exists
        existing_org = db.query(Organization).filter(
            Organization.name == org_data.name,
            Organization.id != org.id
        ).first()
        
        if existing_org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization name already exists"
            )
        
        org.name = org_data.name
    
    if org_data.settings is not None:
        org.settings = org_data.settings
    
    db.commit()
    db.refresh(org)
    
    member_count = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id
    ).count()
    
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        settings=org.settings,
        created_at=org.created_at,
        updated_at=org.updated_at,
        member_count=member_count
    )


# Member management endpoints
@router.get("/current/members", response_model=List[OrganizationMemberResponse])
async def list_organization_members(
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """List all members of the current organization."""
    members = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == context.organization_id
    ).all()
    
    member_responses = []
    for member in members:
        user = db.query(User).filter(User.id == member.user_id).first()
        if user:
            inviter_email = None
            if member.invited_by:
                inviter = db.query(User).filter(User.id == member.invited_by).first()
                inviter_email = inviter.email if inviter else None
            
            member_responses.append(OrganizationMemberResponse(
                id=member.id,
                user_id=member.user_id,
                user_email=user.email,
                user_name=None,  # User model doesn't have a name field yet
                role=member.role.value if hasattr(member.role, 'value') else member.role,
                joined_at=member.joined_at,
                invited_by=member.invited_by
            ))
    
    return member_responses


@router.patch("/members/{member_id}", response_model=OrganizationMemberResponse)
async def update_member_role(
    member_id: UUID,
    member_data: OrganizationMemberUpdate,
    context: CurrentUserContext = Depends(require_org_admin),
    db: Session = Depends(get_db)
):
    """Update a member's role (admin only)."""
    member = db.query(OrganizationMember).filter(
        OrganizationMember.id == member_id,
        OrganizationMember.organization_id == context.organization_id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    
    # Prevent removing the last admin
    if member.role == OrganizationRole.ADMIN and member_data.role != OrganizationRole.ADMIN:
        admin_count = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == context.organization_id,
            OrganizationMember.role == OrganizationRole.ADMIN
        ).count()
        
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last admin"
            )
    
    member.role = member_data.role
    db.commit()
    db.refresh(member)
    
    user = db.query(User).filter(User.id == member.user_id).first()
    
    return OrganizationMemberResponse(
        id=member.id,
        user_id=member.user_id,
        user_email=user.email if user else "",
        user_name=None,  # User model doesn't have a name field yet
        role=member.role.value if hasattr(member.role, 'value') else member.role,
        joined_at=member.joined_at,
        invited_by=member.invited_by
    )


@router.delete("/members/{member_id}")
async def remove_member(
    member_id: UUID,
    context: CurrentUserContext = Depends(require_org_admin),
    db: Session = Depends(get_db)
):
    """Remove a member from the organization (admin only)."""
    member = db.query(OrganizationMember).filter(
        OrganizationMember.id == member_id,
        OrganizationMember.organization_id == context.organization_id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    
    # Prevent removing the last admin
    if member.role == OrganizationRole.ADMIN:
        admin_count = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == context.organization_id,
            OrganizationMember.role == OrganizationRole.ADMIN
        ).count()
        
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last admin"
            )
    
    db.delete(member)
    db.commit()
    
    return {"message": "Member removed successfully"}


# Invitation endpoints
@router.post("/invitations", response_model=OrganizationInvitationResponse)
async def create_invitation(
    invitation_data: OrganizationInvitationCreate,
    context: CurrentUserContext = Depends(require_org_admin),
    db: Session = Depends(get_db)
):
    """Create an invitation to join the organization (admin only)."""
    # Check if user already exists and is a member
    existing_user = db.query(User).filter(User.email == invitation_data.email).first()
    
    if existing_user:
        existing_member = db.query(OrganizationMember).filter(
            OrganizationMember.user_id == existing_user.id,
            OrganizationMember.organization_id == context.organization_id
        ).first()
        
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this organization"
            )
    
    # Check for pending invitation
    existing_invitation = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.email == invitation_data.email,
        OrganizationInvitation.organization_id == context.organization_id,
        OrganizationInvitation.accepted_at.is_(None)
    ).first()
    
    if existing_invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation already sent to this email"
        )
    
    # Create invitation
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    invitation = OrganizationInvitation(
        organization_id=context.organization_id,
        email=invitation_data.email,
        role=invitation_data.role,
        token=token,
        invited_by=context.user.id,
        expires_at=expires_at
    )
    
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    
    return OrganizationInvitationResponse(
        id=invitation.id,
        organization_id=invitation.organization_id,
        organization_name=context.organization.name,
        email=invitation.email,
        role=invitation.role,
        token=invitation.token,
        invited_by_email=context.user.email,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at
    )


@router.get("/invitations", response_model=List[OrganizationInvitationResponse])
async def list_invitations(
    context: CurrentUserContext = Depends(require_org_admin),
    db: Session = Depends(get_db)
):
    """List all pending invitations (admin only)."""
    invitations = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.organization_id == context.organization_id,
        OrganizationInvitation.accepted_at.is_(None),
        OrganizationInvitation.expires_at > datetime.now(timezone.utc)
    ).all()
    
    invitation_responses = []
    for invitation in invitations:
        inviter = db.query(User).filter(User.id == invitation.invited_by).first()
        
        invitation_responses.append(OrganizationInvitationResponse(
            id=invitation.id,
            organization_id=invitation.organization_id,
            organization_name=context.organization.name,
            email=invitation.email,
            role=invitation.role,
            token=invitation.token,
            invited_by_email=inviter.email if inviter else "",
            expires_at=invitation.expires_at,
            created_at=invitation.created_at
        ))
    
    return invitation_responses


@router.delete("/invitations/{invitation_id}")
async def cancel_invitation(
    invitation_id: UUID,
    context: CurrentUserContext = Depends(require_org_admin),
    db: Session = Depends(get_db)
):
    """Cancel an invitation (admin only)."""
    invitation = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.id == invitation_id,
        OrganizationInvitation.organization_id == context.organization_id
    ).first()
    
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found"
        )
    
    db.delete(invitation)
    db.commit()
    
    return {"message": "Invitation cancelled successfully"}


@router.post("/invitations/accept/{token}")
async def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Accept an invitation to join an organization."""
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
            detail="Invitation has expired"
        )
    
    # Check if user email matches invitation email
    if current_user.email != invitation.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation is for a different email address"
        )
    
    # Check if user is already a member
    existing_member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id,
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
        user_id=current_user.id,
        role=invitation.role,
        invited_by=invitation.invited_by
    )
    
    db.add(member)
    
    # Mark invitation as accepted
    invitation.accepted_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return {"message": "Successfully joined the organization"}