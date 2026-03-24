"""OAuth 2.0 / OpenID Connect client configuration for Google and Microsoft SSO."""

from authlib.integrations.starlette_client import OAuth
from app.config import get_settings

settings = get_settings()

oauth = OAuth()

if settings.google_oauth_client_id and settings.google_oauth_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if settings.microsoft_oauth_client_id and settings.microsoft_oauth_client_secret:
    oauth.register(
        name="microsoft",
        client_id=settings.microsoft_oauth_client_id,
        client_secret=settings.microsoft_oauth_client_secret,
        server_metadata_url=(
            f"https://login.microsoftonline.com/{settings.microsoft_oauth_tenant_id}"
            "/v2.0/.well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid email profile"},
    )
