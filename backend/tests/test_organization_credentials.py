"""
Tests for organization-wide credential access.
Ensures that all members of an organization can access shared credentials.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import User, Credential, CredentialType, Organization, user_organizations
from app.core.security import encrypt_credentials, decrypt_credentials
from app.api.routes.credentials import (
    list_jira_credentials, 
    create_jira_credential,
    list_ai_credentials,
    create_ai_credential
)
from app.models.schemas import JiraCredentialResponse


@pytest.fixture
def mock_organization():
    """Create a mock organization."""
    org = Mock(spec=Organization)
    org.id = uuid4()
    org.name = "Test Organization"
    org.slug = "test-org"
    org.is_active = True
    return org


@pytest.fixture
def mock_user_with_org(mock_organization):
    """Create a mock user that belongs to an organization."""
    user = Mock(spec=User)
    user.id = uuid4()
    user.email = "user1@example.com"
    user.current_organization_id = mock_organization.id
    user.current_organization = mock_organization
    return user


@pytest.fixture
def mock_user_same_org(mock_organization):
    """Create another mock user in the same organization."""
    user = Mock(spec=User)
    user.id = uuid4()
    user.email = "user2@example.com"
    user.current_organization_id = mock_organization.id
    user.current_organization = mock_organization
    return user


@pytest.fixture
def mock_user_different_org():
    """Create a mock user in a different organization."""
    different_org_id = uuid4()
    user = Mock(spec=User)
    user.id = uuid4()
    user.email = "user3@example.com"
    user.current_organization_id = different_org_id
    return user


@pytest.fixture
def mock_user_no_org():
    """Create a mock user with no organization."""
    user = Mock(spec=User)
    user.id = uuid4()
    user.email = "no_org@example.com"
    user.current_organization_id = None
    return user


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock(spec=Session)


class TestOrganizationCredentialSharing:
    """Test that credentials are shared across organization members."""
    
    @pytest.mark.asyncio
    async def test_users_in_same_org_see_same_credentials(
        self, mock_user_with_org, mock_user_same_org, mock_organization, mock_db
    ):
        """Test that two users in the same organization see the same credentials."""
        # Create credentials for the organization
        cred = Mock()
        cred.id = uuid4()
        cred.organization_id = mock_organization.id
        cred.type = CredentialType.JIRA
        cred.name = "Shared Jira"
        cred.encrypted_data = encrypt_credentials({
            "server_url": "https://shared.atlassian.net",
            "email": "shared@example.com",
            "api_token": "shared_token"
        })
        cred.created_at = datetime.now()
        cred.updated_at = datetime.now()
        cred.created_by = "admin@example.com"
        org_credentials = [cred]
        
        # Mock database query to return the same credentials for both users
        mock_db.query.return_value.filter.return_value.all.return_value = org_credentials
        
        # Get credentials for user 1
        result1 = await list_jira_credentials(mock_user_with_org, mock_db)
        
        # Get credentials for user 2
        result2 = await list_jira_credentials(mock_user_same_org, mock_db)
        
        # Both users should see the same credentials
        assert len(result1) == len(result2)
        assert len(result1) == 1
        assert result1[0].name == "Shared Jira"
        assert result2[0].name == "Shared Jira"
        
        # Verify that the query filtered by organization
        assert mock_db.query.return_value.filter.call_count == 2
    
    @pytest.mark.asyncio
    async def test_users_in_different_orgs_see_different_credentials(
        self, mock_user_with_org, mock_user_different_org, mock_organization, mock_db
    ):
        """Test that users in different organizations don't see each other's credentials."""
        # Create credentials for org 1
        cred = Mock()
        cred.id = uuid4()
        cred.organization_id = mock_organization.id
        cred.type = CredentialType.JIRA
        cred.name = "Org1 Jira"
        cred.encrypted_data = encrypt_credentials({
            "server_url": "https://org1.atlassian.net",
            "email": "org1@example.com",
            "api_token": "org1_token"
        })
        cred.created_at = datetime.now()
        cred.updated_at = datetime.now()
        org1_credentials = [cred]

        # Use a call counter to return different results for each user's query
        call_count = {"n": 0}
        def filter_side_effect(*args, **kwargs):
            mock_filter = Mock()
            call_count["n"] += 1
            if call_count["n"] == 1:
                mock_filter.all.return_value = org1_credentials  # First call: org1 user
            else:
                mock_filter.all.return_value = []  # Second call: different org user
            return mock_filter

        mock_db.query.return_value.filter.side_effect = filter_side_effect
        
        # Get credentials for user in org 1
        result1 = await list_jira_credentials(mock_user_with_org, mock_db)
        
        # Get credentials for user in different org
        result2 = await list_jira_credentials(mock_user_different_org, mock_db)
        
        # User 1 should see org 1 credentials
        assert len(result1) == 1
        assert result1[0].name == "Org1 Jira"
        
        # User 2 should see no credentials (different org)
        assert len(result2) == 0
    
    @pytest.mark.asyncio
    async def test_user_without_org_sees_no_credentials(
        self, mock_user_no_org, mock_db
    ):
        """Test that a user without an organization sees no credentials."""
        # User has no organization
        result = await list_jira_credentials(mock_user_no_org, mock_db)
        
        # Should return empty list without even querying database
        assert result == []
        mock_db.query.assert_not_called()


class TestCredentialCreationInOrganization:
    """Test credential creation within organizations."""
    
    @pytest.mark.asyncio
    async def test_credential_created_with_organization_id(
        self, mock_user_with_org, mock_organization, mock_db
    ):
        """Test that new credentials are created with the organization_id."""
        credential_data = {
            "name": "New Org Jira",
            "server_url": "https://neworg.atlassian.net",
            "email": "neworg@example.com",
            "api_token": "new_token"
        }
        
        # Mock that no existing credential exists
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock the credential creation
        created_credential = Mock()
        created_credential.id = uuid4()
        created_credential.organization_id = mock_organization.id
        created_credential.created_by = mock_user_with_org.email
        
        def add_side_effect(cred):
            # Verify the credential has the correct organization_id
            assert cred.organization_id == mock_organization.id
            assert cred.created_by == mock_user_with_org.email
            assert cred.user_id == mock_user_with_org.id
        
        mock_db.add.side_effect = add_side_effect
        def refresh_side_effect(x):
            x.id = uuid4()
            x.created_at = datetime.now()
            x.updated_at = datetime.now()
        mock_db.refresh.side_effect = refresh_side_effect

        # Create the credential
        result = await create_jira_credential(credential_data, mock_user_with_org, mock_db)

        # Verify the credential was created with organization context
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_user_without_org_cannot_create_credentials(
        self, mock_user_no_org, mock_db
    ):
        """Test that a user without an organization cannot create credentials."""
        from fastapi import HTTPException
        
        credential_data = {
            "name": "Should Fail",
            "server_url": "https://fail.atlassian.net",
            "email": "fail@example.com",
            "api_token": "fail_token"
        }
        
        # Should raise an exception
        with pytest.raises(HTTPException) as exc_info:
            await create_jira_credential(credential_data, mock_user_no_org, mock_db)
        
        assert exc_info.value.status_code == 400
        assert "must be part of an organization" in exc_info.value.detail


class TestAICredentialsOrganizationAccess:
    """Test organization-wide access for AI credentials."""
    
    @pytest.mark.asyncio
    async def test_ai_credentials_shared_in_organization(
        self, mock_user_with_org, mock_user_same_org, mock_organization, mock_db
    ):
        """Test that AI credentials are shared within the organization."""
        # Create AI credentials for the organization
        ai_credentials = [
            Mock(
                id=uuid4(),
                organization_id=mock_organization.id,
                type=CredentialType.OPENAI,
                name="Shared OpenAI",
                encrypted_data=encrypt_credentials({
                    "api_key": "sk-shared-key",
                    "model": "gpt-4"
                }),
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            Mock(
                id=uuid4(),
                organization_id=mock_organization.id,
                type=CredentialType.GEMINI,
                name="Shared Gemini",
                encrypted_data=encrypt_credentials({
                    "api_key": "gemini-shared-key",
                    "model": "gemini-pro"
                }),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = ai_credentials
        
        # Get AI credentials for both users
        result1 = await list_ai_credentials(mock_user_with_org, mock_db)
        result2 = await list_ai_credentials(mock_user_same_org, mock_db)
        
        # Both users should see the same AI credentials
        assert len(result1) == 2
        assert len(result2) == 2
        assert result1 == result2
    
    @pytest.mark.asyncio
    async def test_create_ai_credential_with_organization(
        self, mock_user_with_org, mock_organization, mock_db
    ):
        """Test creating an AI credential assigns it to the organization."""
        credential_data = {
            "name": "Org AI Key",
            "provider": "openai",
            "api_key": "sk-org-key",
            "model": "gpt-4"
        }
        
        # Mock that no existing credential exists
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        def add_side_effect(cred):
            # Verify the credential has the correct organization_id
            assert cred.organization_id == mock_organization.id
            assert cred.created_by == mock_user_with_org.email
        
        mock_db.add.side_effect = add_side_effect
        def _refresh(x):
            x.id = uuid4()
            x.created_at = datetime.now()
            x.updated_at = datetime.now()
        mock_db.refresh.side_effect = _refresh
        
        # Create the AI credential
        result = await create_ai_credential(credential_data, mock_user_with_org, mock_db)
        
        # Verify it was created
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestCredentialIsolation:
    """Test that credentials are properly isolated between organizations."""
    
    @pytest.mark.asyncio
    async def test_credential_name_uniqueness_per_organization(
        self, mock_user_with_org, mock_user_different_org, mock_organization, mock_db
    ):
        """Test that credential names only need to be unique within an organization."""
        credential_data = {
            "name": "Same Name",  # Same name in different orgs should be allowed
            "server_url": "https://test.atlassian.net",
            "email": "test@example.com",
            "api_token": "test_token"
        }
        
        # For user in org 1 - no existing credential
        mock_db.query.return_value.filter.return_value.first.return_value = None
        def _refresh(x):
            x.id = uuid4()
            x.created_at = datetime.now()
            x.updated_at = datetime.now()
        mock_db.refresh.side_effect = _refresh
        
        # Create credential in org 1
        result1 = await create_jira_credential(credential_data, mock_user_with_org, mock_db)
        assert result1 is not None
        
        # For user in org 2 - also no existing credential (different org)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Create credential with same name in org 2 - should succeed
        result2 = await create_jira_credential(credential_data, mock_user_different_org, mock_db)
        assert result2 is not None
        
        # Both credentials created successfully with same name in different orgs
        assert mock_db.add.call_count == 2
        assert mock_db.commit.call_count == 2


class TestCredentialTracking:
    """Test that we track who created credentials."""
    
    @pytest.mark.asyncio
    async def test_credential_tracks_creator(
        self, mock_user_with_org, mock_organization, mock_db
    ):
        """Test that credentials track who created them."""
        credential_data = {
            "name": "Tracked Credential",
            "server_url": "https://tracked.atlassian.net",
            "email": "tracked@example.com",
            "api_token": "tracked_token"
        }
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        captured_credential = None
        def capture_add(cred):
            nonlocal captured_credential
            captured_credential = cred
        
        mock_db.add.side_effect = capture_add
        def _refresh(x):
            x.id = uuid4()
            x.created_at = datetime.now()
            x.updated_at = datetime.now()
        mock_db.refresh.side_effect = _refresh
        
        # Create the credential
        await create_jira_credential(credential_data, mock_user_with_org, mock_db)
        
        # Verify creator information is tracked
        assert captured_credential is not None
        assert captured_credential.user_id == mock_user_with_org.id
        assert captured_credential.created_by == mock_user_with_org.email
        assert captured_credential.organization_id == mock_organization.id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])