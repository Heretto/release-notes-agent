from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.models.database import get_db, User, OrganizationMember
from app.models.organization import Organization, OrganizationRole
from app.api.dependencies import get_current_active_user, get_current_active_user_with_org
from app.core.security import get_password_hash, verify_password

router = APIRouter(prefix="/account")

class AccountUpdate(BaseModel):
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

class AccountResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: str
    organization_role: Optional[str] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None

@router.get("/me", response_model=AccountResponse)
async def get_account_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user account information including organization role."""
    response = AccountResponse(
        id=str(current_user.id),
        email=current_user.email,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        created_at=current_user.created_at.isoformat()
    )
    
    # Get organization membership if exists
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id
    ).first()
    
    if membership:
        org = db.query(Organization).filter(
            Organization.id == membership.organization_id
        ).first()
        
        role_val = membership.role.value if hasattr(membership.role, 'value') else membership.role
        response.organization_role = role_val.lower() if isinstance(role_val, str) else role_val
        response.organization_id = str(membership.organization_id)
        response.organization_name = org.name if org else None
    
    return response

@router.put("/me")
async def update_account(
    account_data: AccountUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user account information."""
    
    # If updating password, verify current password
    if account_data.new_password:
        if not account_data.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to set a new password"
            )
        
        if not verify_password(account_data.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password strength
        if len(account_data.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 8 characters long"
            )
        
        # Update password
        current_user.password_hash = get_password_hash(account_data.new_password)
    
    # If updating email, check if it's already taken
    if account_data.email and account_data.email != current_user.email:
        existing_user = db.query(User).filter(
            User.email == account_data.email,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        current_user.email = account_data.email
    
    # Commit changes
    db.commit()
    db.refresh(current_user)
    
    return {
        "message": "Account updated successfully",
        "email": current_user.email
    }

@router.delete("/me")
async def delete_account(
    confirm: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete current user account."""
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please confirm account deletion by setting confirm=true"
        )
    
    # Delete user account
    db.delete(current_user)
    db.commit()
    
    return {"message": "Account deleted successfully"}