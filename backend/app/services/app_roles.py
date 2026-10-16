"""Who may write release notes, and who may only review them.

hop-core owns the organization role (ADMIN/MEMBER) and this app must not migrate hop-core's
tables, so the app role lives on `app_user_roles` here. The two are orthogonal: the org role
says who administers the organization, the app role says what the product lets you do.

The default is **reviewer**. Anyone who arrives on their own — an SSO sign-in, a password
registration — can read and comment on release notes and nothing else, until an admin makes
them an author. An admin inviting someone sets their role as part of the invitation, which
is why the table is keyed by email: the role is recorded before the account exists and is
waiting when the invitation is accepted.

Existing people were backfilled as authors by the migration that created the table, so
turning this on did not lock anyone out of their own release notes.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.database import AppRole, AppUserRole


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def role_for(db: Session, organization_id: UUID, email: str) -> str:
    """This person's app role in this organization. Unknown means reviewer."""
    if not organization_id or not email:
        return AppRole.REVIEWER
    row = (
        db.query(AppUserRole)
        .filter(
            AppUserRole.organization_id == organization_id,
            AppUserRole.email == normalize_email(email),
        )
        .first()
    )
    return row.role if row and row.role in AppRole.ALL else AppRole.REVIEWER


def is_author(db: Session, organization_id: UUID, email: str) -> bool:
    return role_for(db, organization_id, email) == AppRole.AUTHOR


def roles_for(db: Session, organization_id: UUID, emails: Iterable[str]) -> Dict[str, str]:
    """Roles for several people at once, for the People page's one list."""
    wanted = {normalize_email(e) for e in emails if e}
    if not wanted:
        return {}
    rows = (
        db.query(AppUserRole)
        .filter(AppUserRole.organization_id == organization_id, AppUserRole.email.in_(wanted))
        .all()
    )
    found = {row.email: row.role for row in rows if row.role in AppRole.ALL}
    return {email: found.get(email, AppRole.REVIEWER) for email in wanted}


def set_role(
    db: Session,
    organization_id: UUID,
    email: str,
    role: str,
    set_by_id: Optional[UUID] = None,
) -> AppUserRole:
    """Give someone a role, creating the row if this is the first time.

    Does not commit: the caller decides when, so setting a role and sending the invitation
    that goes with it are one transaction.
    """
    if role not in AppRole.ALL:
        raise ValueError(f"Unknown role: {role}")

    email = normalize_email(email)
    row = (
        db.query(AppUserRole)
        .filter(AppUserRole.organization_id == organization_id, AppUserRole.email == email)
        .first()
    )
    if row is None:
        row = AppUserRole(organization_id=organization_id, email=email)
        db.add(row)
    row.role = role
    row.set_by_id = set_by_id
    return row


def author_emails(db: Session, organization_id: UUID) -> List[str]:
    """Everyone explicitly marked as an author — used to warn before the last one goes."""
    return [
        row.email
        for row in db.query(AppUserRole.email)
        .filter(
            AppUserRole.organization_id == organization_id,
            AppUserRole.role == AppRole.AUTHOR,
        )
        .all()
    ]
