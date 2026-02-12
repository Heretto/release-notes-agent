import openai
from typing import AsyncIterator, Optional
import asyncio

from app.services.ai_service import AIServiceInterface, GenerationRequest, GenerationResponse

class OpenAIAdapter(AIServiceInterface):
    """OpenAI GPT AI service implementation."""
    
    def __init__(self, api_key: str, model_name: str = "gpt-4-turbo-preview"):
        """Initialize OpenAI adapter with API key and model."""
        if not api_key:
            raise ValueError("API key is empty")
        
        # Strip any whitespace and ensure it's a string
        api_key = str(api_key).strip()
        
        # OpenAI API keys should start with 'sk-'
        if not api_key.startswith("sk-"):
            print(f"[OpenAIAdapter] Warning: API key doesn't start with 'sk-' (got '{api_key[:10] if len(api_key) >= 10 else api_key}...')")
        
        print(f"[OpenAIAdapter] Initializing with model: {model_name}")
        
        try:
            # Initialize OpenAI client
            self.client = openai.AsyncOpenAI(api_key=api_key)
            self.sync_client = openai.OpenAI(api_key=api_key)
            self._model_name = model_name
            print(f"[OpenAIAdapter] Client initialized successfully")
            print(f"[OpenAIAdapter] Using model: {model_name}")
        except Exception as e:
            print(f"[OpenAIAdapter] Failed to initialize client: {e}")
            raise
    
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate content synchronously."""
        try:
            print(f"[OpenAIAdapter] Generating with model: {self._model_name}")
            
            # Create messages array with system and user prompts
            messages = []
            if request.system_prompt:
                messages.append({
                    "role": "system",
                    "content": request.system_prompt
                })
            messages.append({
                "role": "user",
                "content": request.user_prompt
            })
            
            # Create completion parameters
            # Newer models (gpt-4-turbo and later) require max_completion_tokens
            # Older models use max_tokens
            completion_params = {
                "model": self._model_name,
                "messages": messages,
            }
            
            # First attempt with model-appropriate parameter
            try:
                # Check model name to determine which parameter to use
                if any(x in self._model_name.lower() for x in ["gpt-4-turbo", "gpt-4o", "o1", "chatgpt-4o"]):
                    completion_params["max_completion_tokens"] = request.max_tokens or 4096
                else:
                    completion_params["max_tokens"] = request.max_tokens or 4096
                
                response = await self.client.chat.completions.create(**completion_params)
                
            except Exception as e:
                error_msg = str(e)
                # Handle parameter mismatch errors
                if "max_tokens" in error_msg and "max_completion_tokens" in error_msg:
                    # Swap the parameter and retry
                    if "max_completion_tokens" in completion_params:
                        completion_params["max_tokens"] = completion_params.pop("max_completion_tokens")
                        print(f"[OpenAIAdapter] Switching from max_completion_tokens to max_tokens for {self._model_name}")
                    else:
                        completion_params["max_completion_tokens"] = completion_params.pop("max_tokens")
                        print(f"[OpenAIAdapter] Switching from max_tokens to max_completion_tokens for {self._model_name}")
                    
                    # Retry with the other parameter
                    response = await self.client.chat.completions.create(**completion_params)
                else:
                    # Re-raise if it's not a parameter issue
                    raise
            
            # Extract the generated content
            content = response.choices[0].message.content
            
            # Build usage dict
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            
            return GenerationResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=response.choices[0].finish_reason or "stop"
            )
            
        except Exception as e:
            print(f"[OpenAIAdapter] Generation failed: {e}")
            raise
    
    async def generate_stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Generate content with streaming."""
        try:
            print(f"[OpenAIAdapter] Starting stream generation with model: {self._model_name}")
            
            # Create messages array with system and user prompts
            messages = []
            if request.system_prompt:
                messages.append({
                    "role": "system",
                    "content": request.system_prompt
                })
            messages.append({
                "role": "user",
                "content": request.user_prompt
            })
            
            # Create completion parameters for streaming
            completion_params = {
                "model": self._model_name,
                "messages": messages,
                "stream": True
            }
            
            # First attempt with model-appropriate parameter
            try:
                # Check model name to determine which parameter to use
                if any(x in self._model_name.lower() for x in ["gpt-4-turbo", "gpt-4o", "o1", "chatgpt-4o"]):
                    completion_params["max_completion_tokens"] = request.max_tokens or 4096
                else:
                    completion_params["max_tokens"] = request.max_tokens or 4096
                
                stream = await self.client.chat.completions.create(**completion_params)
                
            except Exception as e:
                error_msg = str(e)
                # Handle parameter mismatch errors
                if "max_tokens" in error_msg and "max_completion_tokens" in error_msg:
                    # Swap the parameter and retry
                    if "max_completion_tokens" in completion_params:
                        completion_params["max_tokens"] = completion_params.pop("max_completion_tokens")
                        print(f"[OpenAIAdapter] Switching to max_tokens for streaming with {self._model_name}")
                    else:
                        completion_params["max_completion_tokens"] = completion_params.pop("max_tokens")
                        print(f"[OpenAIAdapter] Switching to max_completion_tokens for streaming with {self._model_name}")
                    
                    # Retry with the other parameter
                    stream = await self.client.chat.completions.create(**completion_params)
                else:
                    # Re-raise if it's not a parameter issue
                    raise
            
            # Stream the content
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"[OpenAIAdapter] Stream generation failed: {e}")
            raise
    
    def get_model_name(self) -> str:
        """Return the model identifier."""
        return self._model_name
    
    async def test_connection(self) -> bool:
        """Test if the API key and model are valid."""
        try:
            # Try a simple completion to test the connection
            messages = [
                {"role": "user", "content": "Say 'test'"}
            ]
            
            # Test with appropriate parameter
            try:
                if any(x in self._model_name.lower() for x in ["gpt-4-turbo", "gpt-4o", "o1", "chatgpt-4o"]):
                    response = await self.client.chat.completions.create(
                        model=self._model_name,
                        messages=messages,
                        max_completion_tokens=10
                    )
                else:
                    response = await self.client.chat.completions.create(
                        model=self._model_name,
                        messages=messages,
                        max_tokens=10
                    )
            except Exception as e:
                error_msg = str(e)
                # If we get a parameter error, try the other one
                if "max_tokens" in error_msg and "max_completion_tokens" in error_msg:
                    # Try the opposite parameter
                    if any(x in self._model_name.lower() for x in ["gpt-4-turbo", "gpt-4o", "o1", "chatgpt-4o"]):
                        response = await self.client.chat.completions.create(
                            model=self._model_name,
                            messages=messages,
                            max_tokens=10
                        )
                    else:
                        response = await self.client.chat.completions.create(
                            model=self._model_name,
                            messages=messages,
                            max_completion_tokens=10
                        )
                else:
                    raise
            
            return bool(response.choices[0].message.content)
        except Exception as e:
            print(f"[OpenAIAdapter] Connection test failed: {e}")
            return False