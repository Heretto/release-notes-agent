"""Who is in this organization, and what the app lets them do.

hop-core owns membership and the organization role; this router owns the *app* role
(author or reviewer) that sits beside it. See app/services/app_roles.py for why that is a
table of ours rather than another value in hop-core's enum.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from hop_core.api.dependencies import require_org_admin
from hop_core.models.organization import OrganizationInvitation

from app.api.dependencies import CurrentUserContext, get_current_active_user_with_org
from app.api.reviewer_access import forget_cached_roles
from app.models.database import AppRole, AppUserRole, User, get_db, user_organizations
from app.services.app_roles import normalize_email, role_for, roles_for, set_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/people")


class MyRoleResponse(BaseModel):
    email: str
    role: str
    is_author: bool
    is_org_admin: bool


class PersonResponse(BaseModel):
    email: str
    role: str
    #: None until they accept an invitation and an account exists.
    user_id: Optional[UUID] = None
    org_role: Optional[str] = None
    #: True when the role is set for an email with no account yet.
    invited: bool = False


class SetRoleRequest(BaseModel):
    email: EmailStr
    role: str = Field(..., pattern=r"^(author|reviewer)$")


@router.get("/me", response_model=MyRoleResponse)
async def my_role(
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db),
):
    """What this app lets the signed-in person do. The browser routes on this."""
    role = role_for(db, context.organization_id, context.user.email)
    return MyRoleResponse(
        email=context.user.email,
        role=role,
        is_author=role == AppRole.AUTHOR,
        is_org_admin=str(getattr(context.organization_role, "value", context.organization_role) or "").upper() == "ADMIN",
    )


@router.get("", response_model=List[PersonResponse])
async def list_people(
    context: CurrentUserContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Everyone in the organization, plus anyone invited but not yet arrived."""
    memberships = db.execute(
        select(user_organizations).where(
            user_organizations.c.organization_id == context.organization_id
        )
    ).all()

    people: List[PersonResponse] = []
    seen: set[str] = set()

    users = {
        user.id: user
        for user in db.query(User).filter(
            User.id.in_([m.user_id for m in memberships] or [None])
        ).all()
    }
    emails = [users[m.user_id].email for m in memberships if m.user_id in users]
    roles = roles_for(db, context.organization_id, emails)

    for membership in memberships:
        user = users.get(membership.user_id)
        if not user:
            continue
        email = normalize_email(user.email)
        seen.add(email)
        people.append(PersonResponse(
            email=user.email,
            role=roles.get(email, AppRole.REVIEWER),
            user_id=user.id,
            org_role=str(getattr(membership.role, "value", membership.role) or "").lower(),
        ))

    # Roles set for an email with no account yet — an invitation whose role is waiting.
    pending = db.query(AppUserRole).filter(
        AppUserRole.organization_id == context.organization_id
    ).all()
    invitations = {
        normalize_email(invitation.email)
        for invitation in db.query(OrganizationInvitation).filter(
            OrganizationInvitation.organization_id == context.organization_id
        ).all()
    }
    for row in pending:
        if row.email in seen:
            continue
        people.append(PersonResponse(
            email=row.email,
            role=row.role,
            invited=True,
            org_role="invited" if row.email in invitations else None,
        ))

    people.sort(key=lambda p: (p.invited, p.email))
    return people


@router.patch("/role", response_model=PersonResponse)
async def set_person_role(
    request: SetRoleRequest,
    context: CurrentUserContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Make someone an author or a reviewer.

    Accepts an address with no account behind it, which is how an admin sets the role of
    someone they are about to invite: the role waits on the email until they accept.
    """
    email = normalize_email(request.email)

    if email == normalize_email(context.user.email) and request.role != AppRole.AUTHOR:
        # Demoting yourself locks you out of the page you did it from, and if you are the
        # only admin-author nobody can undo it.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot make your own account a reviewer. Ask another administrator.",
        )

    row = set_role(db, context.organization_id, email, request.role, set_by_id=context.user.id)
    db.commit()
    db.refresh(row)
    # The access gate caches roles for a few seconds; a promotion should not wait for it.
    forget_cached_roles()
    logger.info("App role for %s set to %s by %s", email, request.role, context.user.email)

    user = db.query(User).filter(User.id.in_(
        select(user_organizations.c.user_id).where(
            user_organizations.c.organization_id == context.organization_id
        )
    )).filter(User.email.ilike(email)).first()

    return PersonResponse(
        email=row.email,
        role=row.role,
        user_id=user.id if user else None,
        invited=user is None,
    )
