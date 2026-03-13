"""
Regression tests for user registration with organization creation.

Ensures that:
1. Registering a new user creates an organization.
2. The user is added as a member of that organization.
3. The user's current_organization_id is set.
4. A custom organization name is used when provided.
5. The ORM model matches the actual database schema.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone

from app.models.database import User, Organization, OrganizationMember, OrganizationRole
from app.models.schemas import UserCreate
from app.api.routes.auth import register, create_slug


class FakeDBSession:
    """Fake database session that tracks added objects and simulates flush/commit."""

    def __init__(self):
        self.added = []
        self._committed = False

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if not hasattr(obj, '_flushed'):
                if hasattr(obj, 'id') and obj.id is None:
                    obj.id = uuid4()
                obj._flushed = True

    def commit(self):
        self._committed = True

    def refresh(self, obj):
        if not hasattr(obj, 'created_at') or obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)

    def query(self, model):
        return FakeQuery(model, self)


class FakeQuery:
    """Fake query that always returns None for .first() (no existing records)."""

    def __init__(self, model, db):
        self.model = model
        self.db = db

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


@pytest.mark.asyncio
async def test_register_creates_organization():
    """Registration should create an organization and link the user to it."""
    db = FakeDBSession()
    user_data = UserCreate(
        email="newuser@example.com",
        password="securepassword123",
        organization_name="My Company"
    )

    result = await register(user_data, db)

    users = [o for o in db.added if isinstance(o, User)]
    orgs = [o for o in db.added if isinstance(o, Organization)]
    members = [o for o in db.added if isinstance(o, OrganizationMember)]

    assert len(users) == 1, "Expected one user to be created"
    assert len(orgs) == 1, "Expected one organization to be created"
    assert len(members) == 1, "Expected one membership to be created"

    user = users[0]
    org = orgs[0]
    member = members[0]

    assert org.name == "My Company"
    assert member.user_id == user.id
    assert member.organization_id == org.id
    assert member.role == OrganizationRole.ADMIN
    assert user.current_organization_id == org.id
    assert db._committed


@pytest.mark.asyncio
async def test_register_creates_default_org_name_from_email():
    """Registration without an org name should derive one from the email."""
    db = FakeDBSession()
    user_data = UserCreate(
        email="jane@bigcorp.com",
        password="securepassword123"
    )

    result = await register(user_data, db)

    orgs = [o for o in db.added if isinstance(o, Organization)]
    assert len(orgs) == 1
    assert orgs[0].name == "jane's Organization"


@pytest.mark.asyncio
async def test_register_sets_current_organization_id():
    """Regression: current_organization_id must be set during registration."""
    db = FakeDBSession()
    user_data = UserCreate(
        email="test@example.com",
        password="securepassword123",
        organization_name="Test Org"
    )

    result = await register(user_data, db)

    users = [o for o in db.added if isinstance(o, User)]
    orgs = [o for o in db.added if isinstance(o, Organization)]

    assert len(users) == 1
    assert len(orgs) == 1

    user = users[0]
    org = orgs[0]

    assert user.current_organization_id is not None, (
        "current_organization_id must be set during registration, "
        "otherwise credential and organization endpoints will fail"
    )
    assert user.current_organization_id == org.id


@pytest.mark.asyncio
async def test_register_creates_org_membership_record():
    """Regression: an OrganizationMember record must be created during registration."""
    db = FakeDBSession()
    user_data = UserCreate(
        email="member@example.com",
        password="securepassword123",
        organization_name="Member Corp"
    )

    result = await register(user_data, db)

    members = [o for o in db.added if isinstance(o, OrganizationMember)]
    assert len(members) == 1, (
        "An OrganizationMember record must be created during registration "
        "to link the user to their organization"
    )

    member = members[0]
    users = [o for o in db.added if isinstance(o, User)]
    orgs = [o for o in db.added if isinstance(o, Organization)]

    assert member.user_id == users[0].id
    assert member.organization_id == orgs[0].id
    assert member.role == OrganizationRole.ADMIN


@pytest.mark.asyncio
async def test_register_creates_valid_slug():
    """Organization slug should be URL-safe."""
    db = FakeDBSession()
    user_data = UserCreate(
        email="slug@example.com",
        password="securepassword123",
        organization_name="My Awesome Company! (2024)"
    )

    result = await register(user_data, db)

    orgs = [o for o in db.added if isinstance(o, Organization)]
    assert len(orgs) == 1
    assert orgs[0].slug == "my-awesome-company-2024"


def test_create_slug():
    """Test the slug creation helper."""
    assert create_slug("My Company") == "my-company"
    assert create_slug("UPPERCASE") == "uppercase"
    assert create_slug("special!@#chars") == "special-chars"
    assert create_slug("  leading-trailing  ") == "leading-trailing"
    assert create_slug("multiple   spaces") == "multiple-spaces"


def test_organization_member_model_uses_correct_table():
    """Regression: OrganizationMember must map to 'organization_members' table, not 'user_organizations'."""
    assert OrganizationMember.__tablename__ == "organization_members", (
        "OrganizationMember must use the 'organization_members' table. "
        "The legacy 'user_organizations' table has a different schema "
        "(composite PK, no id column) and will cause 500 errors."
    )


def test_organization_role_enum_matches_database():
    """Regression: OrganizationRole enum values must be uppercase to match the PG enum."""
    assert OrganizationRole.ADMIN.value == "ADMIN", (
        "OrganizationRole.ADMIN must be 'ADMIN' (uppercase) to match the "
        "PostgreSQL 'organizationrole' enum type in the database."
    )
    assert OrganizationRole.MEMBER.value == "MEMBER", (
        "OrganizationRole.MEMBER must be 'MEMBER' (uppercase) to match the "
        "PostgreSQL 'organizationrole' enum type in the database."
    )


def test_organization_member_has_required_columns():
    """Regression: OrganizationMember model must have id, invited_by columns."""
    column_names = {c.name for c in OrganizationMember.__table__.columns}
    assert "id" in column_names, "OrganizationMember must have an 'id' column"
    assert "user_id" in column_names, "OrganizationMember must have a 'user_id' column"
    assert "organization_id" in column_names, "OrganizationMember must have an 'organization_id' column"
    assert "role" in column_names, "OrganizationMember must have a 'role' column"
    assert "invited_by" in column_names, "OrganizationMember must have an 'invited_by' column"
    assert "joined_at" in column_names, "OrganizationMember must have a 'joined_at' column"


def test_organization_model_has_settings_column():
    """Regression: Organization model must have a 'settings' JSON column.

    The DB 'organizations' table has a 'settings' JSON column. If the ORM model
    is missing it, accessing org.settings (e.g. in GET /organizations/current)
    raises AttributeError and returns a 500 'Failed to Load Organization' error.
    """
    column_names = {c.name for c in Organization.__table__.columns}
    assert "settings" in column_names, (
        "Organization model must have a 'settings' column. "
        "Without it, GET /organizations/current fails with 500."
    )


class TestRegisterIntegration:
    """Integration tests that hit the real database."""

    TEST_EMAIL = "integration_test_register@example.com"
    TEST_ORG = "Integration Test Org"

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clean up test data before and after each test."""
        from app.models.database import SessionLocal
        from sqlalchemy import text

        self.db = SessionLocal()
        self._cleanup()
        yield
        self._cleanup()
        self.db.close()

    def _cleanup(self):
        from sqlalchemy import text
        try:
            user = self.db.query(User).filter(User.email == self.TEST_EMAIL).first()
            if user:
                # Clear FK reference before deleting org
                self.db.execute(
                    text("UPDATE users SET current_organization_id = NULL WHERE id = :uid"),
                    {"uid": str(user.id)}
                )
                self.db.execute(
                    text("DELETE FROM organization_members WHERE user_id = :uid"),
                    {"uid": str(user.id)}
                )
                self.db.execute(
                    text("DELETE FROM organizations WHERE name = :name"),
                    {"name": self.TEST_ORG}
                )
                self.db.delete(user)
                self.db.commit()
        except Exception:
            self.db.rollback()

    @pytest.mark.asyncio
    async def test_register_full_roundtrip(self):
        """End-to-end: register a user and verify all DB records are correct."""
        user_data = UserCreate(
            email=self.TEST_EMAIL,
            password="securepassword123",
            organization_name=self.TEST_ORG
        )

        result = await register(user_data, self.db)

        # Verify user exists in DB
        user = self.db.query(User).filter(User.email == self.TEST_EMAIL).first()
        assert user is not None, "User should exist in the database"
        assert user.current_organization_id is not None, "current_organization_id must be set"

        # Verify organization exists
        org = self.db.query(Organization).filter(
            Organization.id == user.current_organization_id
        ).first()
        assert org is not None, "Organization should exist"
        assert org.name == self.TEST_ORG

        # Verify membership record
        membership = self.db.query(OrganizationMember).filter(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == org.id
        ).first()
        assert membership is not None, "Membership record must exist in organization_members table"
        assert membership.role == OrganizationRole.ADMIN

    @pytest.mark.asyncio
    async def test_admin_role_returned_as_lowercase_in_account_endpoint(self):
        """Regression: /account/me must return 'admin' (lowercase) so the frontend shows the admin panel.

        The DB stores roles as uppercase PG enum ('ADMIN'), but the frontend
        checks `organization_role === 'admin'` (lowercase). If the API returns
        uppercase, the admin panel is hidden even for admin users.
        """
        from app.api.routes.account import get_account_info
        from app.api.dependencies import CurrentUserContext

        user_data = UserCreate(
            email=self.TEST_EMAIL,
            password="securepassword123",
            organization_name=self.TEST_ORG
        )
        user = await register(user_data, self.db)

        # Build the CurrentUserContext the endpoint now expects
        org = self.db.query(Organization).filter(
            Organization.id == user.current_organization_id
        ).first()
        membership = self.db.query(OrganizationMember).filter(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == org.id
        ).first()
        context = CurrentUserContext(
            user=user,
            organization_id=org.id,
            organization=org,
            organization_role=membership.role,
        )

        response = await get_account_info(context, self.db)

        assert response.organization_role == "admin", (
            f"Account endpoint must return lowercase 'admin' for the frontend "
            f"admin panel check, but got {repr(response.organization_role)}"
        )

    @pytest.mark.asyncio
    async def test_admin_role_lowercase_in_login_token(self):
        """Regression: JWT token org_role must be lowercase 'admin' for frontend compatibility."""
        from app.api.routes.auth import login
        from app.models.schemas import LoginRequest
        from app.core.security import decode_token
        from fastapi import Response

        user_data = UserCreate(
            email=self.TEST_EMAIL,
            password="securepassword123",
            organization_name=self.TEST_ORG
        )
        await register(user_data, self.db)

        creds = LoginRequest(email=self.TEST_EMAIL, password="securepassword123")
        response = Response()
        token_resp = await login(creds, response, self.db)

        payload = decode_token(token_resp["access_token"])
        assert payload.get("org_role") == "admin", (
            f"Login token org_role must be lowercase 'admin', "
            f"but got {repr(payload.get('org_role'))}"
        )

    @pytest.mark.asyncio
    async def test_organization_settings_accessible_after_registration(self):
        """Regression: org.settings must be accessible without AttributeError.

        GET /organizations/current accesses org.settings. If the Organization
        model is missing the settings column, this raises AttributeError and
        the admin page shows 'Failed to Load Organization'.
        """
        user_data = UserCreate(
            email=self.TEST_EMAIL,
            password="securepassword123",
            organization_name=self.TEST_ORG
        )
        await register(user_data, self.db)

        user = self.db.query(User).filter(User.email == self.TEST_EMAIL).first()
        org = self.db.query(Organization).filter(
            Organization.id == user.current_organization_id
        ).first()

        assert org is not None, "Organization must exist after registration"
        # This is the access pattern that was failing before the fix
        settings = org.settings or {}
        assert isinstance(settings, dict), (
            f"org.settings should be a dict (or None), got {type(settings)}"
        )
        assert org.name == self.TEST_ORG


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
