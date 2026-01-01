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
    
    # CORS
    cors_origins: str = "http://localhost:4200"
    
    # Server
    api_prefix: str = "/api/v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(',')]

@lru_cache()
def get_settings() -> Settings:
    return Settings()