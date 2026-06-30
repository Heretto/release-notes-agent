import openai
from typing import AsyncIterator, Optional
import logging

from app.services.ai_service import AIServiceInterface, GenerationRequest, GenerationResponse

logger = logging.getLogger(__name__)

DEFAULT_API_VERSION = "2024-05-01-preview"

class AzureAdapter(AIServiceInterface):
    """Azure OpenAI AI service implementation."""

    def __init__(
        self,
        api_key: str,
        azure_endpoint: str,
        deployment_name: str,
        api_version: str = DEFAULT_API_VERSION,
    ):
        if not api_key:
            raise ValueError("API key is empty")
        if not azure_endpoint:
            raise ValueError("Azure endpoint is required")
        if not deployment_name:
            raise ValueError("Deployment name is required")

        azure_endpoint = azure_endpoint.rstrip("/")

        logger.debug("Initializing AzureAdapter: endpoint=%s, deployment=%s", azure_endpoint, deployment_name)

        try:
            self.client = openai.AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=azure_endpoint,
                api_version=api_version,
            )
            self.sync_client = openai.AzureOpenAI(
                api_key=api_key,
                azure_endpoint=azure_endpoint,
                api_version=api_version,
            )
            self._deployment_name = deployment_name
            self._api_version = api_version
        except Exception as e:
            logger.error("Failed to initialize AzureAdapter: %s", e)
            raise

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate content using Azure OpenAI."""
        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.user_prompt})

            response = await self.client.chat.completions.create(
                model=self._deployment_name,
                messages=messages,
                max_tokens=request.max_tokens or 4096,
            )

            content = response.choices[0].message.content
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return GenerationResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=response.choices[0].finish_reason or "stop",
            )
        except Exception as e:
            logger.error("Azure OpenAI generation failed: %s", e)
            raise

    async def generate_stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Generate content with streaming via Azure OpenAI."""
        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.user_prompt})

            stream = await self.client.chat.completions.create(
                model=self._deployment_name,
                messages=messages,
                max_tokens=request.max_tokens or 4096,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("Azure OpenAI stream generation failed: %s", e)
            raise

    def get_model_name(self) -> str:
        return self._deployment_name

    async def test_connection(self) -> bool:
        try:
            response = await self.client.chat.completions.create(
                model=self._deployment_name,
                messages=[{"role": "user", "content": "Say 'test'"}],
                max_tokens=10,
            )
            return bool(response.choices[0].message.content)
        except Exception as e:
            logger.error("Azure OpenAI connection test failed: %s", e)
            return False
