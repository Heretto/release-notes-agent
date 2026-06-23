from typing import Optional
from functools import lru_cache

from hop_core.config import HopCoreSettings


class Settings(HopCoreSettings):
    # Google AI
    google_ai_api_key: Optional[str] = None
    google_ai_model: str = "gemini-2.5-pro"

    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    
    # Jira
    jira_webhook_secret: Optional[str] = None

    # Heretto
    heretto_base_url: str = "https://api.heretto.com"

    # Query limits
    max_query_limit: int = 500
    max_tickets_per_job: int = 500

    # DITA validation: max times invalid DITA is looped back through the LLM
    # before giving up. A generous safety cap — in practice validation passes
    # in the first 1-2 iterations.
    dita_max_correction_iterations: int = 10

    # Override default SMTP from name
    smtp_from_name: str = "Release Notes Agent"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
