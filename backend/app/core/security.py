from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import hmac
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import json

from app.config import get_settings
from app.core.exceptions import AuthenticationError

settings = get_settings()

# Password hashing with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Encryption for credentials
fernet = Fernet(base64.urlsafe_b64encode(settings.encryption_key.encode()[:32].ljust(32, b'0')))

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
    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")

def set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    """Set HttpOnly auth cookies on a response."""
    from fastapi import Response
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


def encrypt_credentials(credentials: Dict[str, Any]) -> bytes:
    """Encrypt credentials for storage."""
    json_str = json.dumps(credentials)
    return fernet.encrypt(json_str.encode())

def decrypt_credentials(encrypted_data: bytes) -> Dict[str, Any]:
    """Decrypt stored credentials."""
    decrypted = fernet.decrypt(encrypted_data)
    return json.loads(decrypted.decode())

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