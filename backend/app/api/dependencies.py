from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from app.models.database import get_db, User
from app.models.organization import Organization, OrganizationMember, OrganizationRole
from app.core.security import decode_token
from app.core.exceptions import AuthenticationError
from dataclasses import dataclass
from uuid import UUID

security = HTTPBearer()

@dataclass
class CurrentUserContext:
    """Context for the current authenticated user."""
    user: User
    organization_id: Optional[UUID] = None
    organization: Optional[Organization] = None
    organization_role: Optional[OrganizationRole] = None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    
    try:
        payload = decode_token(token)
        
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token payload")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise AuthenticationError("User not found")
        
        if not user.is_active:
            raise AuthenticationError("User is inactive")
        
        return user
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> CurrentUserContext:
    """Get current user with organization context."""
    token = credentials.credentials
    
    try:
        payload = decode_token(token)
        
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid token payload")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise AuthenticationError("User not found")
        
        if not user.is_active:
            raise AuthenticationError("User is inactive")
        
        # Get organization context from token or user's memberships
        org_id = payload.get("org_id")
        org = None
        org_role = None
        
        if org_id:
            # Verify user is member of this organization
            membership = db.query(OrganizationMember).filter(
                OrganizationMember.user_id == user.id,
                OrganizationMember.organization_id == org_id
            ).first()
            
            if membership:
                org = db.query(Organization).filter(Organization.id == org_id).first()
                org_role = membership.role
        else:
            # Get user's first organization as default
            membership = db.query(OrganizationMember).filter(
                OrganizationMember.user_id == user.id
            ).first()
            
            if membership:
                org_id = membership.organization_id
                org = db.query(Organization).filter(Organization.id == org_id).first()
                org_role = membership.role
        
        return CurrentUserContext(
            user=user,
            organization_id=org_id,
            organization=org,
            organization_role=org_role
        )
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure user is active (backward compatibility)."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_active_user_with_org(
    context: CurrentUserContext = Depends(get_current_user_context)
) -> CurrentUserContext:
    """Get current user with organization context."""
    if not context.user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    if not context.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization"
        )
    
    return context

async def require_org_admin(
    context: CurrentUserContext = Depends(get_current_active_user_with_org)
) -> CurrentUserContext:
    """Ensure user is an organization admin."""
    if context.organization_role != OrganizationRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return context

async def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure user is a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user