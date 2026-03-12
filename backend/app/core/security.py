from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import hmac
import secrets
import jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64
import json

from app.config import get_settings
from app.core.exceptions import AuthenticationError

settings = get_settings()

# Password hashing with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Encryption for credentials — derive a proper 256-bit key via PBKDF2
_ENCRYPTION_SALT = b"release-notes-agent-credential-encryption"

def _derive_fernet_key(passphrase: str) -> bytes:
    """Derive a Fernet key from a passphrase using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_ENCRYPTION_SALT,
        iterations=480_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

def _derive_legacy_fernet_key(passphrase: str) -> bytes:
    """Legacy key derivation (truncate/pad to 32 bytes). Used for migration only."""
    return base64.urlsafe_b64encode(passphrase.encode()[:32].ljust(32, b'0'))

if len(settings.encryption_key) < 16:
    raise ValueError(
        "ENCRYPTION_KEY must be at least 16 characters. "
        "Generate a strong key, e.g.: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

fernet = Fernet(_derive_fernet_key(settings.encryption_key))
_legacy_fernet = Fernet(_derive_legacy_fernet_key(settings.encryption_key))

def _is_sha256_hash(hashed_password: str) -> bool:
    """Check if a hash is a legacy SHA256 hex digest (64 hex chars)."""
    return len(hashed_password) == 64 and all(c in '0123456789abcdef' for c in hashed_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash. Supports legacy SHA256 and bcrypt."""
    if _is_sha256_hash(hashed_password):
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)

def needs_rehash(hashed_password: str) -> bool:
    """Check if a password hash should be upgraded to bcrypt."""
    return _is_sha256_hash(hashed_password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.PyJWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")

def generate_csrf_token() -> str:
    """Generate a cryptographically random CSRF token."""
    return secrets.token_urlsafe(32)


def set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    """Set HttpOnly auth cookies and a readable CSRF cookie on a response."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1",
        max_age=settings.jwt_access_token_expire_minutes * 60,
        domain=settings.cookie_domain,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        domain=settings.cookie_domain,
    )
    # CSRF token — readable by JavaScript so the frontend can send it as a header.
    # The double-submit pattern validates that the cookie value matches the header.
    response.set_cookie(
        key="csrf_token",
        value=generate_csrf_token(),
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1",
        max_age=settings.jwt_access_token_expire_minutes * 60,
        domain=settings.cookie_domain,
    )


def clear_auth_cookies(response) -> None:
    """Clear auth cookies from a response."""
    response.delete_cookie(
        key="access_token",
        path="/api/v1",
        domain=settings.cookie_domain,
    )
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        domain=settings.cookie_domain,
    )
    response.delete_cookie(
        key="csrf_token",
        path="/api/v1",
        domain=settings.cookie_domain,
    )


def encrypt_credentials(credentials: Dict[str, Any]) -> bytes:
    """Encrypt credentials for storage (always uses current PBKDF2-derived key)."""
    json_str = json.dumps(credentials)
    return fernet.encrypt(json_str.encode())

def decrypt_credentials(encrypted_data: bytes) -> Dict[str, Any]:
    """Decrypt stored credentials.

    Tries the current PBKDF2-derived key first. If that fails, falls back to
    the legacy truncate-and-pad key so existing data can still be read.
    """
    try:
        decrypted = fernet.decrypt(encrypted_data)
        return json.loads(decrypted.decode())
    except InvalidToken:
        # Try legacy key derivation for data encrypted before the migration
        decrypted = _legacy_fernet.decrypt(encrypted_data)
        return json.loads(decrypted.decode())

import ipaddress
import socket
from urllib.parse import urlparse

# IP ranges that must never be targeted by user-supplied URLs
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("10.0.0.0/8"),         # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),      # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),     # RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),     # link-local / cloud metadata
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique-local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]


def validate_server_url(url: str) -> str:
    """Validate a user-supplied server URL to prevent SSRF.

    Checks:
      - Scheme is https (or http in development mode)
      - Hostname resolves to a public IP (not loopback, private, or link-local)
      - No bare IP addresses pointing at internal ranges

    Returns the validated URL, or raises ValueError with a user-safe message.
    """
    parsed = urlparse(url)

    # Scheme check
    allowed_schemes = ("https",)
    if settings.app_env == "development":
        allowed_schemes = ("https", "http")
    if parsed.scheme not in allowed_schemes:
        raise ValueError(f"URL must use {' or '.join(allowed_schemes)}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a hostname")

    # Resolve hostname and check all resulting IPs
    try:
        addrinfos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}")

    for family, _, _, _, sockaddr in addrinfos:
        ip = ipaddress.ip_address(sockaddr[0])
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError("URL must not point to a private or internal address")

    return url


def verify_jira_webhook_signature(body: bytes, signature: Optional[str]) -> bool:
    """Verify Jira webhook signature."""
    if not signature or not settings.jira_webhook_secret:
        return False
    
    expected_signature = hmac.new(
        settings.jira_webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, f"sha256={expected_signature}")