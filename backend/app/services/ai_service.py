from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from pydantic import BaseModel

class GenerationRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    max_tokens: Optional[int] = 4096
    temperature: Optional[float] = 0.7
    
class GenerationResponse(BaseModel):
    content: str
    model: str
    usage: dict
    finish_reason: str

class AIServiceInterface(ABC):
    """Abstract interface for AI service implementations."""
    
    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate content synchronously."""
        pass
    
    @abstractmethod
    async def generate_stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Generate content with streaming."""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier."""
        pass

class AIServiceFactory:
    """Factory for creating AI service instances."""
    
    @staticmethod
    def create(provider: str, api_key: str, model: Optional[str] = None) -> AIServiceInterface:
        """Create an AI service instance based on provider."""
        if provider == "gemini":
            from app.services.gemini_adapter import GeminiAdapter
            return GeminiAdapter(api_key=api_key, model_name=model or "gemini-2.5-pro")
        elif provider == "anthropic":
            from app.services.anthropic_adapter import AnthropicAdapter
            return AnthropicAdapter(api_key=api_key, model_name=model or "claude-sonnet-4-20250514")
        elif provider == "openai":
            from app.services.openai_adapter import OpenAIAdapter
            return OpenAIAdapter(api_key=api_key, model_name=model or "gpt-4-turbo-preview")
        else:
            raise ValueError(f"Unknown AI provider: {provider}")