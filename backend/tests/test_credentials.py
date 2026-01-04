"""
Tests for credentials management functionality.
Tests ensure that credentials are properly created, encrypted, and retrieved.
"""
import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import User, Credential, CredentialType
from app.core.security import encrypt_credentials, decrypt_credentials
from app.api.routes.credentials import list_jira_credentials, create_jira_credential
from app.models.schemas import JiraCredentialResponse


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = Mock(spec=User)
    user.id = uuid4()
    user.email = "test@example.com"
    user.organization_id = uuid4()
    return user


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def sample_jira_creds():
    """Sample Jira credentials for testing."""
    return {
        "server_url": "https://test.atlassian.net",
        "email": "test@example.com",
        "api_token": "test_api_token_123"
    }


class TestCredentialEncryption:
    """Test credential encryption and decryption."""
    
    def test_encrypt_decrypt_credentials(self, sample_jira_creds):
        """Test that credentials can be encrypted and decrypted successfully."""
        # Encrypt credentials
        encrypted = encrypt_credentials(sample_jira_creds)
        assert encrypted is not None
        assert isinstance(encrypted, bytes)
        assert encrypted != str(sample_jira_creds).encode()  # Should not be plain text
        
        # Decrypt credentials
        decrypted = decrypt_credentials(encrypted)
        assert decrypted == sample_jira_creds
        assert decrypted["server_url"] == sample_jira_creds["server_url"]
        assert decrypted["email"] == sample_jira_creds["email"]
        assert decrypted["api_token"] == sample_jira_creds["api_token"]


class TestJiraCredentialsList:
    """Test Jira credentials listing functionality."""
    
    @pytest.mark.asyncio
    async def test_list_jira_credentials_empty(self, mock_user, mock_db):
        """Test listing credentials when none exist."""
        # Setup mock to return empty list
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        # Call the function
        result = await list_jira_credentials(mock_user, mock_db)
        
        # Assertions
        assert result == []
        mock_db.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_jira_credentials_with_data(self, mock_user, mock_db, sample_jira_creds):
        """Test listing credentials with existing data."""
        # Create mock credential
        mock_cred = Mock(spec=Credential)
        mock_cred.id = uuid4()
        mock_cred.type = CredentialType.JIRA
        mock_cred.name = "Test Jira"
        mock_cred.encrypted_data = encrypt_credentials(sample_jira_creds)
        mock_cred.created_at = datetime.now()
        mock_cred.updated_at = datetime.now()
        
        # Setup mock to return credential
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_cred]
        
        # Call the function
        result = await list_jira_credentials(mock_user, mock_db)
        
        # Assertions
        assert len(result) == 1
        assert isinstance(result[0], JiraCredentialResponse)
        assert result[0].name == "Test Jira"
        assert result[0].server_url == sample_jira_creds["server_url"]
        assert result[0].email == sample_jira_creds["email"]
    
    @pytest.mark.asyncio
    async def test_list_jira_credentials_handles_decryption_error(self, mock_user, mock_db):
        """Test that decryption errors are handled gracefully."""
        # Create mock credential with invalid encrypted data
        mock_cred = Mock(spec=Credential)
        mock_cred.id = uuid4()
        mock_cred.type = CredentialType.JIRA
        mock_cred.name = "Bad Credential"
        mock_cred.encrypted_data = b"invalid_encrypted_data"  # This will fail to decrypt
        mock_cred.created_at = datetime.now()
        mock_cred.updated_at = datetime.now()
        
        # Setup mock to return credential
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_cred]
        
        # Call the function - should not raise exception
        result = await list_jira_credentials(mock_user, mock_db)
        
        # Should skip the bad credential
        assert result == []
    
    @pytest.mark.asyncio
    async def test_list_filters_by_user_id(self, mock_user, mock_db):
        """Test that credentials are filtered by user ID."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        await list_jira_credentials(mock_user, mock_db)
        
        # Check that filter was called with correct user_id
        filter_call = mock_db.query.return_value.filter.call_args
        assert mock_user.id in str(filter_call)


class TestJiraCredentialsCreate:
    """Test Jira credentials creation functionality."""
    
    @pytest.mark.asyncio
    async def test_create_jira_credential_success(self, mock_user, mock_db):
        """Test successful creation of Jira credential."""
        # Setup
        credential_data = {
            "name": "My Jira",
            "server_url": "https://test.atlassian.net",
            "email": "test@example.com",
            "api_token": "test_token"
        }
        
        # Mock that no existing credential exists
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock the new credential after creation
        new_cred_id = uuid4()
        
        def set_id(cred):
            cred.id = new_cred_id
            cred.created_at = datetime.now()
            cred.updated_at = datetime.now()
        
        mock_db.refresh.side_effect = set_id
        
        # Call the function
        result = await create_jira_credential(credential_data, mock_user, mock_db)
        
        # Assertions
        assert result.name == credential_data["name"]
        assert result.server_url == credential_data["server_url"]
        assert result.email == credential_data["email"]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_jira_credential_duplicate_name(self, mock_user, mock_db):
        """Test that duplicate names are rejected."""
        from fastapi import HTTPException
        
        credential_data = {
            "name": "Existing Jira",
            "server_url": "https://test.atlassian.net",
            "email": "test@example.com",
            "api_token": "test_token"
        }
        
        # Mock that an existing credential exists
        existing_cred = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_cred
        
        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await create_jira_credential(credential_data, mock_user, mock_db)
        
        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail


class TestAICredentials:
    """Test AI provider credentials functionality."""
    
    @pytest.mark.asyncio
    async def test_list_ai_credentials_mixed_providers(self, mock_user, mock_db):
        """Test listing AI credentials from different providers."""
        # Create mock credentials for different providers
        openai_cred = Mock(spec=Credential)
        openai_cred.id = uuid4()
        openai_cred.type = CredentialType.OPENAI
        openai_cred.name = "OpenAI Key"
        
        gemini_cred = Mock(spec=Credential)
        gemini_cred.id = uuid4()
        gemini_cred.type = CredentialType.GEMINI
        gemini_cred.name = "Gemini Key"
        
        # This would be tested similarly for the AI credentials endpoint
        # Implementation depends on having the proper endpoint structure


# Integration test to ensure frontend can retrieve credentials
class TestCredentialsIntegration:
    """Integration tests for credential retrieval."""
    
    @pytest.mark.asyncio
    async def test_credentials_endpoint_returns_correct_format(self, mock_user, mock_db):
        """Test that the endpoint returns data in the format expected by frontend."""
        # Create a credential with all expected fields
        mock_cred = Mock(spec=Credential)
        mock_cred.id = uuid4()
        mock_cred.type = CredentialType.JIRA
        mock_cred.name = "Integration Test"
        mock_cred.encrypted_data = encrypt_credentials({
            "server_url": "https://integration.test",
            "email": "integration@test.com",
            "api_token": "int_token"
        })
        mock_cred.created_at = datetime.now()
        mock_cred.updated_at = datetime.now()
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_cred]
        
        result = await list_jira_credentials(mock_user, mock_db)
        
        # Verify all fields needed by frontend are present
        assert hasattr(result[0], 'id')
        assert hasattr(result[0], 'name')
        assert hasattr(result[0], 'server_url')
        assert hasattr(result[0], 'email')
        assert hasattr(result[0], 'api_token')
        assert hasattr(result[0], 'created_at')
        assert hasattr(result[0], 'updated_at')


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])