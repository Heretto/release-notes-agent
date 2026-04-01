import google.generativeai as genai
from typing import AsyncIterator
import asyncio
import logging

from app.services.ai_service import AIServiceInterface, GenerationRequest, GenerationResponse

logger = logging.getLogger(__name__)

class GeminiAdapter(AIServiceInterface):
    """Google Gemini AI service implementation."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro"):
        genai.configure(api_key=api_key)

        # The SDK handles the "models/" prefix internally
        if model_name.startswith("models/"):
            model_name = model_name[7:]

        clean_model_name = model_name.strip()

        logger.debug("Initializing GeminiAdapter with model: %s", clean_model_name)

        try:
            self.model = genai.GenerativeModel(clean_model_name)
            self._model_name = clean_model_name
            logger.debug("GeminiAdapter initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize GeminiAdapter: %s", e)
            raise
    
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate content synchronously."""
        try:
            # Combine system and user prompts
            full_prompt = f"{request.system_prompt}\n\n{request.user_prompt}"
            
            # Generate content
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=request.max_tokens,
                    temperature=request.temperature
                )
            )
            
            return GenerationResponse(
                content=response.text,
                model=self._model_name,
                usage={
                    "prompt_tokens": 0,  # Gemini doesn't provide token counts in the same way
                    "completion_tokens": 0,
                    "total_tokens": 0
                },
                finish_reason="stop"
            )
        except Exception as e:
            raise Exception(f"Gemini generation error: {str(e)}")
    
    async def generate_stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Generate content with streaming."""
        try:
            # Combine system and user prompts
            full_prompt = f"{request.system_prompt}\n\n{request.user_prompt}"
            
            # Generate content with streaming
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=request.max_tokens,
                    temperature=request.temperature
                ),
                stream=True
            )
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            raise Exception(f"Gemini streaming error: {str(e)}")
    
    def get_model_name(self) -> str:
        """Return the model identifier."""
        return self._model_name