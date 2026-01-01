#!/usr/bin/env python3
"""Test Gemini adapter with real API key."""

import asyncio
import os
from app.services.gemini_adapter import GeminiAdapter
from app.services.ai_service import GenerationRequest

async def test_gemini():
    # Get API key from environment
    api_key = os.getenv('GOOGLE_AI_API_KEY')
    if not api_key:
        print("No GOOGLE_AI_API_KEY found in environment")
        return
    
    print(f"Using API key: ...{api_key[-4:]}")
    
    # Test with different model names
    test_models = [
        "gemini-1.5-pro-latest",
        "gemini-1.5-pro",
        "gemini-1.5-flash-latest", 
    ]
    
    for model_name in test_models:
        print(f"\n{'='*60}")
        print(f"Testing model: {model_name}")
        print('='*60)
        
        try:
            # Initialize adapter
            adapter = GeminiAdapter(api_key=api_key, model_name=model_name)
            print(f"✓ Adapter initialized successfully with {model_name}")
            
            # Test generation
            request = GenerationRequest(
                system_prompt="You are a helpful assistant.",
                user_prompt="Say 'Hello, I am working!' in exactly 5 words.",
                max_tokens=50,
                temperature=0.1
            )
            
            response = await adapter.generate(request)
            print(f"✓ Generation successful!")
            print(f"  Model: {response.model}")
            print(f"  Response: {response.content}")
            
        except Exception as e:
            print(f"✗ Error with {model_name}: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())