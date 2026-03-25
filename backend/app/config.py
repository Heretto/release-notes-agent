from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache

class Settings(BaseSettings):
    # Application
    app_env: str = "development"
    app_secret_key: str
    app_debug: bool = False
    
    # Database
    database_url: str
    redis_url: str
    
    # Authentication
    jwt_secret_key: str
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"
    
    # Encryption
    encryption_key: str
    
    # Google AI
    google_ai_api_key: Optional[str] = None
    google_ai_model: str = "gemini-2.5-pro"
    
    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    
    # Jira
    jira_webhook_secret: Optional[str] = None
    
    # Heretto
    heretto_base_url: str = "https://api.heretto.com"
    
    # SSO / OAuth
    google_oauth_client_id: Optional[str] = None  # Google Sign-In: client ID only, no secret needed
    microsoft_oauth_client_id: Optional[str] = None
    microsoft_oauth_client_secret: Optional[str] = None
    microsoft_oauth_tenant_id: str = "common"
    oauth_redirect_base_url: Optional[str] = None  # e.g. "https://app.example.com"

    # Cookies
    cookie_secure: bool = False  # Set True in production behind HTTPS
    cookie_domain: Optional[str] = None  # None = current domain only

    # CORS
    cors_origins: str = "http://localhost:4200"
    
    # Query limits
    max_query_limit: int = 500
    max_tickets_per_job: int = 500

    # Server
    api_prefix: str = "/api/v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(',')]

@lru_cache()
def get_settings() -> Settings:
    return Settings()