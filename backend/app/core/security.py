"""Security utilities — re-exports from hop-core plus domain-specific functions."""

# Re-export everything from hop-core
from hop_core.core.security import (  # noqa: F401
    verify_password,
    get_password_hash,
    needs_rehash,
    create_access_token,
    create_refresh_token,
    decode_token,
    create_password_reset_token,
    decode_password_reset_token,
    generate_csrf_token,
    set_auth_cookies,
    clear_auth_cookies,
    encrypt_credentials,
    decrypt_credentials,
    validate_server_url,
)

# Domain-specific: Jira webhook signature verification
import hashlib
import hmac
from typing import Optional

from app.config import get_settings


def verify_jira_webhook_signature(body: bytes, signature: Optional[str]) -> bool:
    """Verify Jira webhook signature."""
    settings = get_settings()
    if not signature or not settings.jira_webhook_secret:
        return False

    expected_signature = hmac.new(
        settings.jira_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, f"sha256={expected_signature}")
