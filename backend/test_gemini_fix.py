#!/usr/bin/env python3
"""Test the Gemini adapter fix."""

import asyncio
import os
from app.services.gemini_adapter import GeminiAdapter
from app.services.ai_service import GenerationRequest

async def test():
    api_key = os.getenv('GOOGLE_AI_API_KEY')
    if not api_key:
        print("No API key found")
        return
    
    print("Testing with cleaned model name...")
    print("="*60)
    
    # Test with the model name that was failing
    model_name = "gemini-1.5-pro-latest"
    
    try:
        adapter = GeminiAdapter(api_key=api_key, model_name=model_name)
        print(f"✓ Adapter created successfully")
        
        request = GenerationRequest(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Hello, the fix is working!' if you can respond.",
            max_tokens=50,
            temperature=0.1
        )
        
        print(f"Sending test request...")
        response = await adapter.generate(request)
        print(f"✓ Response received!")
        print(f"  Content: {response.content}")
        print(f"  Model: {response.model}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())