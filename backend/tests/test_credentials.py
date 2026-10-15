"""Tests for credential encryption.

The CRUD, listing and connection-testing tests that used to live here covered this app's
own credentials router. That router is gone: hop-core's generic one serves /credentials now
(see AGENTS.md), and its behaviour is hop-core's to test. What remains app code — and so
still belongs here — is the Fernet round trip the stored payloads depend on.
"""

import pytest

from app.core.security import encrypt_credentials, decrypt_credentials


@pytest.fixture
def sample_jira_creds():
    """A payload shaped like hop-core's registered `jira` credential spec."""
    return {
        "server_url": "https://test.atlassian.net",
        "email": "test@example.com",
        "api_token": "test_api_token_123",
    }


class TestCredentialEncryption:
    """Test credential encryption and decryption."""

    def test_encrypt_decrypt_credentials(self, sample_jira_creds):
        """Test that credentials can be encrypted and decrypted successfully."""
        encrypted = encrypt_credentials(sample_jira_creds)
        assert encrypted is not None
        assert isinstance(encrypted, bytes)
        assert encrypted != str(sample_jira_creds).encode()  # Should not be plain text

        decrypted = decrypt_credentials(encrypted)
        assert decrypted == sample_jira_creds
        assert decrypted["server_url"] == sample_jira_creds["server_url"]
        assert decrypted["email"] == sample_jira_creds["email"]
        assert decrypted["api_token"] == sample_jira_creds["api_token"]
