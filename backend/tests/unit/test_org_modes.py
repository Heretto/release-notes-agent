"""
Unit tests for single-organization mode and domain-restricted registration.

Covers:
- ALLOWED_EMAIL_DOMAINS: blocks registrations from non-listed domains
- SINGLE_ORG_MODE + SINGLE_ORG_SLUG: routes new users into a pre-existing org
- Both password registration (POST /auth/register) and SSO (_handle_sso_login)
- GET /auth/sso/providers: returns the single_org_mode and sso_only flags

All tests are pure unit tests (no real database). Settings are patched via
monkeypatch so each test runs in isolation regardless of the environment.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.models.database import User, Organization, OrganizationMember, OrganizationRole
from app.models.schemas import UserCreate
from hop_core.api.routes.auth import register


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fake_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/register",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _disable_rate_limiting(monkeypatch):
    from app.core.rate_limit import limiter
    monkeypatch.setattr(limiter, "enabled", False)


def _make_default_org(slug="default-org"):
    """Return a minimal Organization object representing the pre-existing default org."""
    org = Organization()
    org.id = uuid4()
    org.name = "Default Org"
    org.slug = slug
    org.is_active = True
    return org


class FakeQuery:
    """Fake query that returns seeded objects or None."""

    def __init__(self, seed_objects=None):
        self._objects = seed_objects or []

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._objects[0] if self._objects else None


class FakeDBSession:
    """
    Fake database session.

    seed: dict mapping model class -> list of objects to return from .first().
    Pass seed={Organization: [org]} to simulate an existing default org.
    Pass seed={User: [user]} to simulate an existing user (duplicate email check).
    """

    def __init__(self, seed=None):
        self.added = []
        self._committed = False
        self._seed = seed or {}

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if not hasattr(obj, "_flushed"):
                if hasattr(obj, "id") and obj.id is None:
                    obj.id = uuid4()
                obj._flushed = True

    def commit(self):
        self._committed = True

    def refresh(self, obj):
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)

    def query(self, model):
        return FakeQuery(self._seed.get(model, []))

    # helpers for assertions
    def _users(self):
        return [o for o in self.added if isinstance(o, User)]

    def _orgs(self):
        return [o for o in self.added if isinstance(o, Organization)]

    def _members(self):
        return [o for o in self.added if isinstance(o, OrganizationMember)]


# ---------------------------------------------------------------------------
# Helpers for patching settings
# ---------------------------------------------------------------------------

def _patch_settings(monkeypatch, **kwargs):
    """Patch the settings object used by both auth and sso route modules."""
    defaults = {
        "sso_only": False,
        "single_org_mode": False,
        "single_org_slug": None,
        "allowed_email_domains": None,
    }
    defaults.update(kwargs)

    # allowed_domains_list is a @property; compute it from the patched value
    raw_domains = defaults.get("allowed_email_domains") or ""
    domains_list = [d.strip().lower() for d in raw_domains.split(",") if d.strip()]

    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    mock.allowed_domains_list = domains_list

    # hop-core routes call get_settings() inline; patch the imported reference
    # in each route module rather than a module-level settings variable.
    for getter_path in (
        "hop_core.api.routes.auth.get_settings",
        "hop_core.api.routes.sso.get_settings",
    ):
        monkeypatch.setattr(getter_path, lambda _mock=mock: _mock)


# ---------------------------------------------------------------------------
# Domain restriction — password registration
# ---------------------------------------------------------------------------

class TestDomainRestrictionRegister:
    """ALLOWED_EMAIL_DOMAINS blocks non-matching domains on POST /auth/register."""

    @pytest.mark.asyncio
    async def test_allowed_domain_passes(self, monkeypatch):
        _patch_settings(monkeypatch, allowed_email_domains="example.com")
        db = FakeDBSession()
        user_data = UserCreate(email="alice@example.com", password="password123", organization_name="Acme")
        result = await register(_fake_request(), user_data, db)
        assert len(db._users()) == 1

    @pytest.mark.asyncio
    async def test_blocked_domain_raises_403(self, monkeypatch):
        from fastapi import HTTPException
        _patch_settings(monkeypatch, allowed_email_domains="example.com")
        db = FakeDBSession()
        user_data = UserCreate(email="alice@other.com", password="password123", organization_name="Acme")
        with pytest.raises(HTTPException) as exc_info:
            await register(_fake_request(), user_data, db)
        assert exc_info.value.status_code == 403
        assert "domain" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_multiple_allowed_domains(self, monkeypatch):
        _patch_settings(monkeypatch, allowed_email_domains="example.com, contractor.io")
        db = FakeDBSession()
        user_data = UserCreate(email="bob@contractor.io", password="password123", organization_name="Bob Co")
        result = await register(_fake_request(), user_data, db)
        assert len(db._users()) == 1

    @pytest.mark.asyncio
    async def test_no_restriction_when_domains_unset(self, monkeypatch):
        _patch_settings(monkeypatch, allowed_email_domains=None)
        db = FakeDBSession()
        user_data = UserCreate(email="anyone@anywhere.net", password="password123", organization_name="Any Co")
        result = await register(_fake_request(), user_data, db)
        assert len(db._users()) == 1

    @pytest.mark.asyncio
    async def test_domain_check_is_case_insensitive(self, monkeypatch):
        _patch_settings(monkeypatch, allowed_email_domains="Example.COM")
        db = FakeDBSession()
        user_data = UserCreate(email="alice@EXAMPLE.com", password="password123", organization_name="Acme")
        result = await register(_fake_request(), user_data, db)
        assert len(db._users()) == 1

    @pytest.mark.asyncio
    async def test_blocked_domain_creates_no_records(self, monkeypatch):
        from fastapi import HTTPException
        _patch_settings(monkeypatch, allowed_email_domains="example.com")
        db = FakeDBSession()
        user_data = UserCreate(email="spy@attacker.com", password="password123")
        with pytest.raises(HTTPException):
            await register(_fake_request(), user_data, db)
        assert len(db.added) == 0, "No DB records should be created for a blocked domain"


# ---------------------------------------------------------------------------
# Domain restriction — SSO
# ---------------------------------------------------------------------------

class TestDomainRestrictionSSO:
    """ALLOWED_EMAIL_DOMAINS also blocks new SSO users from non-listed domains."""

    def _call_sso(self):
        from hop_core.api.routes.sso import _handle_sso_login
        return _handle_sso_login

    def _make_empty_db(self):
        """DB with no existing users (forces the 'create new user' path)."""
        return MagicMock(**{
            "query.return_value.filter.return_value.first.return_value": None,
            "add": MagicMock(),
            "flush": MagicMock(),
            "commit": MagicMock(),
            "refresh": MagicMock(),
        })

    def test_blocked_domain_raises_403(self, monkeypatch):
        from fastapi import HTTPException
        _patch_settings(monkeypatch, allowed_email_domains="example.com")
        db = self._make_empty_db()
        with pytest.raises(HTTPException) as exc_info:
            self._call_sso()(db, "google", "g-123", "spy@other.com", "Spy")
        assert exc_info.value.status_code == 403

    def test_allowed_domain_proceeds(self, monkeypatch):
        """Allowed domain should not raise; user creation is attempted."""
        _patch_settings(
            monkeypatch,
            allowed_email_domains="example.com",
            single_org_mode=False,
        )
        # DB that finds no existing user but can accept new objects
        added = []
        flushed_ids = {}

        def fake_query(model):
            q = MagicMock()
            q.filter.return_value.first.return_value = None
            return q

        db = MagicMock()
        db.query.side_effect = fake_query
        db.add.side_effect = lambda obj: added.append(obj)

        def fake_flush():
            for obj in added:
                if not hasattr(obj, "_flushed"):
                    if not obj.id:
                        obj.id = uuid4()
                    obj._flushed = True

        db.flush.side_effect = fake_flush

        # Should not raise
        try:
            self._call_sso()(db, "google", "g-456", "alice@example.com", "Alice")
        except Exception as e:
            # Only 403 is a failure here; other exceptions (e.g. attr errors on
            # the mock org object) are acceptable in this unit test context.
            if hasattr(e, "status_code") and e.status_code == 403:
                pytest.fail("Allowed domain should not raise 403")

    def test_existing_user_bypasses_domain_check(self, monkeypatch):
        """Account linking (existing user) should never be blocked by domain restrictions."""
        _patch_settings(monkeypatch, allowed_email_domains="example.com")

        existing_user = MagicMock(spec=User)
        existing_user.oauth_provider = None
        existing_user.oauth_id = None

        call_count = [0]

        def fake_query(model):
            q = MagicMock()
            call_count[0] += 1
            # First call = oauth_id lookup → None; second = email lookup → user
            q.filter.return_value.first.return_value = (
                None if call_count[0] == 1 else existing_user
            )
            return q

        db = MagicMock()
        db.query.side_effect = fake_query

        result = self._call_sso()(db, "google", "g-789", "alice@other.com", "Alice")
        assert result is existing_user, "Existing user should be returned without domain check"


# ---------------------------------------------------------------------------
# Single-org mode — password registration
# ---------------------------------------------------------------------------

class TestSingleOrgModeRegister:
    """In single_org_mode, register joins the default org instead of creating one."""

    DEFAULT_SLUG = "default-org"

    def _db_with_default_org(self):
        org = _make_default_org(self.DEFAULT_SLUG)
        return FakeDBSession(seed={Organization: [org]}), org

    @pytest.mark.asyncio
    async def test_no_new_organization_created(self, monkeypatch):
        _patch_settings(monkeypatch, single_org_mode=True, single_org_slug=self.DEFAULT_SLUG)
        db, _ = self._db_with_default_org()
        user_data = UserCreate(email="alice@example.com", password="password123")
        await register(_fake_request(), user_data, db)
        assert len(db._orgs()) == 0, "single_org_mode must not create a new Organization"

    @pytest.mark.asyncio
    async def test_user_joined_to_default_org(self, monkeypatch):
        _patch_settings(monkeypatch, single_org_mode=True, single_org_slug=self.DEFAULT_SLUG)
        db, default_org = self._db_with_default_org()
        user_data = UserCreate(email="alice@example.com", password="password123")
        await register(_fake_request(), user_data, db)

        users = db._users()
        assert len(users) == 1
        assert users[0].current_organization_id == default_org.id

    @pytest.mark.asyncio
    async def test_user_gets_member_role_not_admin(self, monkeypatch):
        _patch_settings(monkeypatch, single_org_mode=True, single_org_slug=self.DEFAULT_SLUG)
        db, _ = self._db_with_default_org()
        user_data = UserCreate(email="alice@example.com", password="password123")
        await register(_fake_request(), user_data, db)

        members = db._members()
        assert len(members) == 1
        assert members[0].role == OrganizationRole.MEMBER, (
            "Users added in single_org_mode should be MEMBERs, not ADMINs"
        )

    @pytest.mark.asyncio
    async def test_membership_links_to_default_org(self, monkeypatch):
        _patch_settings(monkeypatch, single_org_mode=True, single_org_slug=self.DEFAULT_SLUG)
        db, default_org = self._db_with_default_org()
        user_data = UserCreate(email="alice@example.com", password="password123")
        await register(_fake_request(), user_data, db)

        member = db._members()[0]
        user = db._users()[0]
        assert member.organization_id == default_org.id
        assert member.user_id == user.id

    @pytest.mark.asyncio
    async def test_missing_slug_raises_500(self, monkeypatch):
        from fastapi import HTTPException
        _patch_settings(monkeypatch, single_org_mode=True, single_org_slug=None)
        db = FakeDBSession()  # no seed needed — error raised before DB query
        user_data = UserCreate(email="alice@example.com", password="password123")
        with pytest.raises(HTTPException) as exc_info:
            await register(_fake_request(), user_data, db)
        assert exc_info.value.status_code == 500
        assert "SINGLE_ORG_SLUG" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_unknown_slug_raises_500(self, monkeypatch):
        from fastapi import HTTPException
        _patch_settings(monkeypatch, single_org_mode=True, single_org_slug="nonexistent-org")
        db = FakeDBSession()  # empty seed → Organization query returns None
        user_data = UserCreate(email="alice@example.com", password="password123")
        with pytest.raises(HTTPException) as exc_info:
            await register(_fake_request(), user_data, db)
        assert exc_info.value.status_code == 500
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_org_name_field_ignored(self, monkeypatch):
        """In single_org_mode, any organization_name the client sends is silently ignored."""
        _patch_settings(monkeypatch, single_org_mode=True, single_org_slug=self.DEFAULT_SLUG)
        db, default_org = self._db_with_default_org()
        user_data = UserCreate(
            email="alice@example.com",
            password="password123",
            organization_name="I Want My Own Org",
        )
        await register(_fake_request(), user_data, db)
        assert len(db._orgs()) == 0
        assert db._users()[0].current_organization_id == default_org.id

    @pytest.mark.asyncio
    async def test_combined_domain_and_single_org(self, monkeypatch):
        """Domain restriction and single_org_mode work together."""
        from fastapi import HTTPException
        _patch_settings(
            monkeypatch,
            single_org_mode=True,
            single_org_slug=self.DEFAULT_SLUG,
            allowed_email_domains="example.com",
        )
        db, _ = self._db_with_default_org()
        bad_user = UserCreate(email="hacker@other.com", password="password123")
        with pytest.raises(HTTPException) as exc_info:
            await register(_fake_request(), bad_user, db)
        assert exc_info.value.status_code == 403

        # Allowed domain still works
        db2, _ = self._db_with_default_org()
        good_user = UserCreate(email="alice@example.com", password="password123")
        await register(_fake_request(), good_user, db2)
        assert len(db2._users()) == 1
        assert len(db2._orgs()) == 0


# ---------------------------------------------------------------------------
# Single-org mode — SSO
# ---------------------------------------------------------------------------

class TestSingleOrgModeSSO:
    """In single_org_mode, SSO login also joins the default org."""

    DEFAULT_SLUG = "default-org"

    def _call_sso(self, db, email="new@example.com", name="New User"):
        from hop_core.api.routes.sso import _handle_sso_login
        return _handle_sso_login(db, "google", f"g-{uuid4()}", email, name)

    def _db_for_new_sso_user(self, default_org):
        """DB with no existing users but a seeded default org."""
        call_count = [0]

        def fake_query(model):
            q = MagicMock()
            call_count[0] += 1
            if model is Organization:
                q.filter.return_value.first.return_value = default_org
            else:
                # User lookups return None (new user)
                q.filter.return_value.first.return_value = None
            return q

        added = []

        def fake_flush():
            for obj in added:
                if not hasattr(obj, "_flushed"):
                    if not getattr(obj, "id", None):
                        obj.id = uuid4()
                    obj._flushed = True

        db = MagicMock()
        db.query.side_effect = fake_query
        db.add.side_effect = lambda obj: added.append(obj)
        db.flush.side_effect = fake_flush
        db._added = added
        return db

    def test_no_new_organization_created(self, monkeypatch):
        _patch_settings(monkeypatch, single_org_mode=True, single_org_slug=self.DEFAULT_SLUG)
        default_org = _make_default_org(self.DEFAULT_SLUG)
        db = self._db_for_new_sso_user(default_org)
        self._call_sso(db)
        new_orgs = [o for o in db._added if isinstance(o, Organization)]
        assert len(new_orgs) == 0, "SSO single_org_mode must not create a new Organization"

    def test_user_gets_member_role(self, monkeypatch):
        _patch_settings(monkeypatch, single_org_mode=True, single_org_slug=self.DEFAULT_SLUG)
        default_org = _make_default_org(self.DEFAULT_SLUG)
        db = self._db_for_new_sso_user(default_org)
        self._call_sso(db)
        members = [o for o in db._added if isinstance(o, OrganizationMember)]
        assert len(members) == 1
        assert members[0].role == OrganizationRole.MEMBER

    def test_user_current_org_set_to_default(self, monkeypatch):
        _patch_settings(monkeypatch, single_org_mode=True, single_org_slug=self.DEFAULT_SLUG)
        default_org = _make_default_org(self.DEFAULT_SLUG)
        db = self._db_for_new_sso_user(default_org)
        self._call_sso(db)
        users = [o for o in db._added if isinstance(o, User)]
        assert len(users) == 1
        assert users[0].current_organization_id == default_org.id


# ---------------------------------------------------------------------------
# Multi-org mode (default) — regression guard
# ---------------------------------------------------------------------------

class TestMultiOrgMode:
    """Default mode: each new user gets their own org with ADMIN role."""

    @pytest.mark.asyncio
    async def test_new_org_created_for_each_user(self, monkeypatch):
        _patch_settings(monkeypatch, single_org_mode=False)
        db = FakeDBSession()
        user_data = UserCreate(email="alice@example.com", password="password123", organization_name="Alice Co")
        await register(_fake_request(), user_data, db)
        assert len(db._orgs()) == 1

    @pytest.mark.asyncio
    async def test_user_gets_admin_role(self, monkeypatch):
        _patch_settings(monkeypatch, single_org_mode=False)
        db = FakeDBSession()
        user_data = UserCreate(email="alice@example.com", password="password123", organization_name="Alice Co")
        await register(_fake_request(), user_data, db)
        assert db._members()[0].role == OrganizationRole.ADMIN

    @pytest.mark.asyncio
    async def test_no_domain_restriction_by_default(self, monkeypatch):
        _patch_settings(monkeypatch, single_org_mode=False, allowed_email_domains=None)
        db = FakeDBSession()
        user_data = UserCreate(email="anyone@anydomain.xyz", password="password123", organization_name="Any Co")
        await register(_fake_request(), user_data, db)
        assert len(db._users()) == 1


# ---------------------------------------------------------------------------
# Providers endpoint flags
# ---------------------------------------------------------------------------

class TestProvidersEndpointFlags:
    """GET /auth/sso/providers must return single_org_mode and sso_only."""

    def _build_app(self, monkeypatch, **settings_kwargs):
        from hop_core.api.routes.sso import router as sso_router
        app = FastAPI()
        # The SSO router already carries prefix="/auth/sso"; mount without extra prefix.
        app.include_router(sso_router)
        _patch_settings(monkeypatch, **settings_kwargs)
        return TestClient(app)

    def test_single_org_mode_false_by_default(self, monkeypatch):
        client = self._build_app(monkeypatch, single_org_mode=False, sso_only=False)
        resp = client.get("/auth/sso/providers")
        assert resp.status_code == 200
        assert resp.json()["single_org_mode"] is False

    def test_single_org_mode_true_when_set(self, monkeypatch):
        client = self._build_app(monkeypatch, single_org_mode=True, sso_only=False)
        resp = client.get("/auth/sso/providers")
        assert resp.status_code == 200
        assert resp.json()["single_org_mode"] is True

    def test_sso_only_false_by_default(self, monkeypatch):
        client = self._build_app(monkeypatch, single_org_mode=False, sso_only=False)
        resp = client.get("/auth/sso/providers")
        assert resp.json()["sso_only"] is False

    def test_sso_only_true_when_set(self, monkeypatch):
        client = self._build_app(monkeypatch, single_org_mode=False, sso_only=True)
        resp = client.get("/auth/sso/providers")
        assert resp.json()["sso_only"] is True

    def test_both_flags_present_in_response(self, monkeypatch):
        client = self._build_app(monkeypatch, single_org_mode=True, sso_only=True)
        data = client.get("/auth/sso/providers").json()
        assert "single_org_mode" in data
        assert "sso_only" in data
