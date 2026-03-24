"""SSO authentication routes for Google and Microsoft OAuth 2.0 / OpenID Connect."""

import re
import uuid
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.oauth import oauth
from app.core.rate_limit import limiter
from app.core.security import create_access_token, create_refresh_token, set_auth_cookies
from app.models.database import get_db, User, OrganizationMember
from app.models.organization import Organization, OrganizationRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/sso")
settings = get_settings()


def _frontend_url(path: str = "/") -> str:
    """Return the base URL for frontend redirects."""
    if settings.oauth_redirect_base_url:
        return settings.oauth_redirect_base_url.rstrip("/") + path
    # Fall back to first CORS origin
    origins = settings.cors_origins_list
    if origins:
        return origins[0].rstrip("/") + path
    return path


def _safe_return_url(url: str | None) -> str:
    """Validate and return a safe relative URL, defaulting to /dashboard."""
    if not url:
        return "/dashboard"
    try:
        decoded = url if isinstance(url, str) else str(url)
        if decoded.startswith("/") and not decoded.startswith("//") and "://" not in decoded:
            return decoded
    except Exception:
        pass
    return "/dashboard"


def _create_slug(name: str) -> str:
    """Create a URL-safe slug from a name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


def _build_token_data(user: User, db: Session) -> dict:
    """Build JWT token data including org context, mirroring auth.py login logic."""
    from sqlalchemy import select
    from app.models.database import user_organizations

    token_data = {"sub": str(user.id), "email": user.email}

    stmt = select(user_organizations).where(user_organizations.c.user_id == user.id)
    user_orgs = db.execute(stmt).fetchall()

    if user_orgs:
        default_org = user_orgs[0]
        role_val = default_org.role.value if hasattr(default_org.role, "value") else default_org.role
        token_data["org_id"] = str(default_org.organization_id)
        token_data["org_role"] = role_val.lower() if isinstance(role_val, str) else role_val

    return token_data


def _handle_sso_login(
    db: Session,
    provider: str,
    oauth_id: str,
    email: str,
    name: str | None,
) -> User:
    """Resolve or create a user from SSO credentials.

    1. Existing SSO user (same provider + oauth_id) → return them.
    2. Existing email user (no SSO link yet) → link and return.
    3. New user → create user + personal organization.
    """
    # 1. Look up by provider + oauth_id
    user = db.query(User).filter(
        User.oauth_provider == provider,
        User.oauth_id == oauth_id,
    ).first()
    if user:
        return user

    # 2. Look up by email (account linking)
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.oauth_provider = provider
        user.oauth_id = oauth_id
        db.commit()
        return user

    # 3. Create new user + organization
    user = User(
        email=email,
        password_hash=None,
        oauth_provider=provider,
        oauth_id=oauth_id,
        is_active=True,
    )
    db.add(user)
    db.flush()

    org_name = f"{name}'s Organization" if name else f"{email.split('@')[0]}'s Organization"
    base_slug = _create_slug(org_name)
    slug = base_slug
    counter = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    org = Organization(id=uuid.uuid4(), name=org_name, slug=slug)
    db.add(org)
    db.flush()

    user.current_organization_id = org.id

    membership = OrganizationMember(
        user_id=user.id,
        organization_id=org.id,
        role=OrganizationRole.ADMIN,
    )
    db.add(membership)
    db.commit()
    db.refresh(user)

    return user


# ---------------------------------------------------------------------------
# Public endpoint: which providers are available?
# ---------------------------------------------------------------------------

@router.get("/providers")
async def get_sso_providers():
    """Return which SSO providers are configured."""
    return {
        "google": hasattr(oauth, "google") and oauth.google is not None,
        "microsoft": hasattr(oauth, "microsoft") and oauth.microsoft is not None,
    }


# ---------------------------------------------------------------------------
# Google SSO
# ---------------------------------------------------------------------------

@router.get("/google")
@limiter.limit("10/minute")
async def sso_google_login(request: Request, return_url: str | None = None):
    """Redirect to Google's authorization page."""
    if not hasattr(oauth, "google") or oauth.google is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google SSO not configured")

    safe_return = _safe_return_url(return_url)
    request.session["sso_return_url"] = safe_return

    redirect_uri = _frontend_url(f"/api/v1/auth/sso/google/callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def sso_google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle the callback from Google after authorization."""
    if not hasattr(oauth, "google") or oauth.google is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google SSO not configured")

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        logger.warning("Google SSO token exchange failed: %s", e)
        return RedirectResponse(url=_frontend_url("/login?sso_error=token_exchange_failed"))

    userinfo = token.get("userinfo")
    if not userinfo:
        return RedirectResponse(url=_frontend_url("/login?sso_error=no_user_info"))

    email = userinfo.get("email")
    if not email or not userinfo.get("email_verified"):
        return RedirectResponse(url=_frontend_url("/login?sso_error=email_not_verified"))

    user = _handle_sso_login(
        db,
        provider="google",
        oauth_id=userinfo["sub"],
        email=email,
        name=userinfo.get("name"),
    )

    return _build_auth_redirect(request, user, db)


# ---------------------------------------------------------------------------
# Microsoft SSO
# ---------------------------------------------------------------------------

@router.get("/microsoft")
@limiter.limit("10/minute")
async def sso_microsoft_login(request: Request, return_url: str | None = None):
    """Redirect to Microsoft's authorization page."""
    if not hasattr(oauth, "microsoft") or oauth.microsoft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Microsoft SSO not configured")

    safe_return = _safe_return_url(return_url)
    request.session["sso_return_url"] = safe_return

    redirect_uri = _frontend_url(f"/api/v1/auth/sso/microsoft/callback")
    return await oauth.microsoft.authorize_redirect(request, redirect_uri)


@router.get("/microsoft/callback")
async def sso_microsoft_callback(request: Request, db: Session = Depends(get_db)):
    """Handle the callback from Microsoft after authorization."""
    if not hasattr(oauth, "microsoft") or oauth.microsoft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Microsoft SSO not configured")

    try:
        token = await oauth.microsoft.authorize_access_token(request)
    except Exception as e:
        logger.warning("Microsoft SSO token exchange failed: %s", e)
        return RedirectResponse(url=_frontend_url("/login?sso_error=token_exchange_failed"))

    userinfo = token.get("userinfo")
    if not userinfo:
        return RedirectResponse(url=_frontend_url("/login?sso_error=no_user_info"))

    email = userinfo.get("email") or userinfo.get("preferred_username")
    if not email:
        return RedirectResponse(url=_frontend_url("/login?sso_error=email_not_verified"))

    user = _handle_sso_login(
        db,
        provider="microsoft",
        oauth_id=userinfo["sub"],
        email=email,
        name=userinfo.get("name"),
    )

    return _build_auth_redirect(request, user, db)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_auth_redirect(request: Request, user: User, db: Session) -> RedirectResponse:
    """Build JWT tokens, set cookies, and redirect to the frontend."""
    token_data = _build_token_data(user, db)
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return_url = request.session.pop("sso_return_url", "/dashboard")
    redirect_url = _frontend_url(f"/auth/sso/complete?return_url={return_url}")

    response = RedirectResponse(url=redirect_url, status_code=302)
    set_auth_cookies(response, access_token, refresh_token)
    return response
