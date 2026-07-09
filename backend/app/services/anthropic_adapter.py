import anthropic
from typing import AsyncIterator, Optional
import asyncio
import logging

from app.services.ai_service import AIServiceInterface, GenerationRequest, GenerationResponse

logger = logging.getLogger(__name__)

class AnthropicAdapter(AIServiceInterface):
    """Anthropic Claude AI service implementation."""

    def __init__(self, api_key: str, model_name: str = "claude-sonnet-4-5-20250929"):
        if not api_key:
            raise ValueError("API key is empty")

        api_key = str(api_key).strip()

        if not api_key.startswith("sk-"):
            logger.warning("Anthropic API key has unexpected prefix")

        logger.debug("Initializing AnthropicAdapter with model: %s", model_name)

        try:
            self.client = anthropic.AsyncAnthropic(api_key=api_key)
            self.sync_client = anthropic.Anthropic(api_key=api_key)
            self._model_name = model_name
            logger.debug("AnthropicAdapter initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize AnthropicAdapter: %s", e)
            raise
    
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate content synchronously."""
        try:
            logger.debug("AnthropicAdapter generating with model: %s", self._model_name)

            # Create message with system and user prompts.
            create_kwargs = {
                "model": self._model_name,
                "max_tokens": request.max_tokens or 4096,
                "temperature": request.temperature if request.temperature is not None else 0.7,
                "system": request.system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": request.user_prompt
                    }
                ],
            }
            try:
                response = await self.client.messages.create(**create_kwargs)
            except Exception as e:
                # Newer models (e.g. claude-sonnet-5) reject temperature as deprecated.
                # Retry once without it rather than failing the whole generation.
                if "temperature" in str(e).lower() and "temperature" in create_kwargs:
                    create_kwargs.pop("temperature", None)
                    response = await self.client.messages.create(**create_kwargs)
                else:
                    raise
            
            # Extract text content from the response. Some models (e.g. claude-sonnet-5)
            # return TextBlocks whose `.text` is None alongside the real content block,
            # so guard against None rather than concatenating it.
            content = ""
            if response.content:
                for block in response.content:
                    text = getattr(block, 'text', None)
                    if text:
                        content += text
            
            return GenerationResponse(
                content=content,
                model=self._model_name,
                usage={
                    "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                    "completion_tokens": response.usage.output_tokens if response.usage else 0,
                    "total_tokens": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0
                },
                finish_reason=response.stop_reason or "stop"
            )
        except Exception as e:
            raise Exception(f"Anthropic generation error: {str(e)}")
    
    async def generate_stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Generate content with streaming."""
        try:
            # Create streaming message
            create_kwargs = {
                "model": self._model_name,
                "max_tokens": request.max_tokens or 4096,
                "temperature": request.temperature if request.temperature is not None else 0.7,
                "system": request.system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": request.user_prompt
                    }
                ],
            }
            try:
                async with self.client.messages.stream(**create_kwargs) as stream:
                    async for chunk in stream.text_stream:
                        yield chunk
            except Exception as e:
                # Newer models (e.g. claude-sonnet-5) reject temperature as deprecated.
                # The validation error is raised before any chunk streams, so retry cleanly.
                if "temperature" in str(e).lower() and "temperature" in create_kwargs:
                    create_kwargs.pop("temperature", None)
                    async with self.client.messages.stream(**create_kwargs) as stream:
                        async for chunk in stream.text_stream:
                            yield chunk
                else:
                    raise
                    
        except Exception as e:
            raise Exception(f"Anthropic streaming error: {str(e)}")
    
    def get_model_name(self) -> str:
        """Return the model identifier."""
        return self._model_name
    
    async def test_connection(self) -> dict:
        """Test the Anthropic API connection."""
        try:
            response = await self.client.messages.create(
                model=self._model_name,
                max_tokens=10,
                messages=[
                    {
                        "role": "user",
                        "content": "Say 'test'"
                    }
                ]
            )
            
            content = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, 'text'):
                        content += block.text
            
            return {
                "success": True,
                "model": self._model_name,
                "response": content
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }