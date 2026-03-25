"""OAuth 2.0 / OpenID Connect client configuration for Microsoft SSO.

Google uses a client-side ID token flow (Google Identity Services) that
does not require a server-side OAuth client — only a client ID for token
validation. See sso.py for the Google token verification endpoint.
"""

from authlib.integrations.starlette_client import OAuth
from app.config import get_settings

settings = get_settings()

oauth = OAuth()

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
