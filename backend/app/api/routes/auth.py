from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models.database import get_db, User, OrganizationMember, user_organizations
from app.models.organization import Organization, OrganizationRole
from app.models.schemas import UserCreate, UserResponse, LoginRequest, TokenResponse, OrganizationCreate, UserOrganizationInfo, ForgotPasswordRequest, ResetPasswordRequest
from app.core.security import (
    verify_password,
    get_password_hash,
    needs_rehash,
    create_access_token,
    create_refresh_token,
    decode_token,
    set_auth_cookies,
    clear_auth_cookies,
    create_password_reset_token,
    decode_password_reset_token,
)
from app.core.exceptions import AuthenticationError
from app.config import get_settings
from app.core.rate_limit import limiter
import logging
import uuid
import re

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth")
settings = get_settings()

def create_slug(name: str) -> str:
    """Create a URL-safe slug from a name."""
    # Convert to lowercase and replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower())
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug

@router.post("/register", response_model=UserResponse)
@limiter.limit("20/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user with organization."""
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if organization name is provided and unique
    org_name = getattr(user_data, 'organization_name', None)
    if not org_name:
        # Default organization name from email
        org_name = user_data.email.split('@')[0] + "'s Organization"

    # Check if organization name already exists
    existing_org = db.query(Organization).filter(Organization.name == org_name).first()
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name already exists"
        )

    # Create slug for organization
    base_slug = create_slug(org_name)
    slug = base_slug
    counter = 1

    # Ensure unique slug
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Create new user
    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password)
    )

    db.add(new_user)
    db.flush()  # Flush to get the user ID

    # Create organization
    new_organization = Organization(
        id=uuid.uuid4(),
        name=org_name,
        slug=slug
    )

    db.add(new_organization)
    db.flush()  # Flush to get the organization ID

    # Set user's current organization
    new_user.current_organization_id = new_organization.id

    # Add user as admin of the organization
    membership = OrganizationMember(
        user_id=new_user.id,
        organization_id=new_organization.id,
        role=OrganizationRole.ADMIN
    )
    db.add(membership)
    db.commit()
    db.refresh(new_user)

    return new_user

@router.post("/login")
@limiter.limit("30/minute")
async def login(
    request: Request,
    credentials: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """Login and receive JWT tokens (set as HttpOnly cookies + returned in body)."""
    # Find user
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not user.password_hash or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Transparently upgrade legacy SHA256 hashes to bcrypt
    if needs_rehash(user.password_hash):
        user.password_hash = get_password_hash(credentials.password)
        db.commit()

    # Get user's organizations
    from sqlalchemy import select
    stmt = select(user_organizations).where(user_organizations.c.user_id == user.id)
    user_orgs = db.execute(stmt).fetchall()

    # Include organization info in token (use first org as default)
    token_data = {
        "sub": str(user.id),
        "email": user.email
    }

    # Build organizations list for response
    org_list = []
    if user_orgs:
        # Add default organization to token
        default_org = user_orgs[0]
        default_role = default_org.role.value if hasattr(default_org.role, 'value') else default_org.role
        token_data["org_id"] = str(default_org.organization_id)
        token_data["org_role"] = default_role.lower() if isinstance(default_role, str) else default_role

        # Build full org list
        for uo in user_orgs:
            org = db.query(Organization).filter(Organization.id == uo.organization_id).first()
            if org:
                role_val = uo.role.value if hasattr(uo.role, 'value') else uo.role
                if isinstance(role_val, str):
                    role_val = role_val.lower()
                org_list.append(UserOrganizationInfo(
                    id=org.id,
                    name=org.name,
                    slug=org.slug,
                    role=role_val,
                ))

    # Create tokens
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    expires_at = int((datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)).timestamp())

    # Set HttpOnly cookies
    set_auth_cookies(response, access_token, refresh_token)

    # Also return tokens in body for API clients / tests
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "organizations": org_list,
    }

@router.post("/refresh")
@limiter.limit("60/minute")
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token (from cookie or body)."""
    # Try cookie first, then request body
    token = request.cookies.get("refresh_token")
    if not token:
        try:
            body = await request.json()
            token = body.get("refresh_token")
        except Exception:
            pass

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )

    try:
        payload = decode_token(token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        # Rebuild token with org context so refreshed tokens keep org info
        from sqlalchemy import select
        token_data = {"sub": str(user.id), "email": user.email}

        if user.current_organization_id:
            from app.models.database import user_organizations
            stmt = select(user_organizations).where(
                user_organizations.c.user_id == user.id,
                user_organizations.c.organization_id == user.current_organization_id,
            )
            membership = db.execute(stmt).first()
            if membership:
                role_val = membership.role.value if hasattr(membership.role, 'value') else membership.role
                token_data["org_id"] = str(user.current_organization_id)
                token_data["org_role"] = role_val.lower() if isinstance(role_val, str) else role_val

        # Create new tokens
        new_access_token = create_access_token(data=token_data)
        new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
        expires_at = int((datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)).timestamp())

        # Set HttpOnly cookies
        set_auth_cookies(response, new_access_token, new_refresh_token)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_at": expires_at,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@router.post("/logout")
async def logout(response: Response):
    """Logout: clear auth cookies."""
    clear_auth_cookies(response)
    return {"message": "Successfully logged out"}


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Request a password reset email."""
    if not settings.smtp_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset is not available. Contact your administrator.",
        )

    user = db.query(User).filter(User.email == body.email).first()
    if user and user.is_active:
        token = create_password_reset_token(user.email)
        try:
            from app.services.email_service import send_password_reset_email
            await send_password_reset_email(user.email, token)
        except Exception:
            logger.exception("Failed to send password reset email")

    # Always return success to prevent email enumeration
    return {"message": "If an account with that email exists, a password reset link has been sent."}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Reset password using a valid reset token."""
    try:
        email = decode_password_reset_token(body.token)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset token",
        )

    user.password_hash = get_password_hash(body.new_password)
    db.commit()

    return {"message": "Password has been reset successfully."}
