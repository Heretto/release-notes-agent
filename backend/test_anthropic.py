#!/usr/bin/env python3
"""Test Anthropic/Claude integration."""
from dotenv import load_dotenv
load_dotenv()

import os
api_key = os.getenv("ANTHROPIC_API_KEY")
print(f"API key is: {api_key}")

import asyncio
from app.services.anthropic_adapter import AnthropicAdapter
from app.services.ai_service import GenerationRequest

async def main():
    # You'll need to replace this with your actual API key for testing

    # Create adapter
    adapter = AnthropicAdapter(
        api_key=api_key,
        model_name="claude-sonnet-4-5-20250929" #claude-sonnet-4-5-20250929
    )
    
    # Test simple generation
    request = GenerationRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="Say hello and confirm you're Claude.",
        max_tokens=100,
        temperature=0.5
    )
    
    try:
        response = await adapter.generate(request)
        print("Success!")
        print(f"Model: {response.model}")
        print(f"Response: {response.content}")
        print(f"Usage: {response.usage}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())