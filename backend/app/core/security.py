"""Security utilities — re-exports from hop-core plus domain-specific functions."""

# Re-export everything from hop-core
from hop_core.core.security import (  # noqa: F401
    verify_password,
    get_password_hash,
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


def verify_webhook_signature(body: bytes, signature: Optional[str], secret: Optional[str]) -> bool:
    """Is this body signed with this secret?

    HMAC-SHA256 over the raw body, compared in constant time. Refuses when either the
    signature or the secret is missing, so a deployment that never set one cannot be driven
    by unsigned requests.
    """
    if not signature or not secret:
        return False

    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, f"sha256={expected}")


def verify_jira_webhook_signature(body: bytes, signature: Optional[str]) -> bool:
    """Verify against the deployment-wide Jira webhook secret.

    Only the legacy un-addressed endpoint uses this. A webhook that names its configuration
    is verified against that configuration's own secret instead — one secret per webhook,
    so holding one cannot start work in another organization.
    """
    return verify_webhook_signature(body, signature, get_settings().jira_webhook_secret)
