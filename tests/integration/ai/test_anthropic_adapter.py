#!/usr/bin/env python3
"""Test Anthropic/Claude integration."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from setup_path import setup_test_paths
setup_test_paths()

from dotenv import load_dotenv
load_dotenv()

import asyncio
import pytest
from app.services.anthropic_adapter import AnthropicAdapter
from app.services.ai_service import GenerationRequest

async def test_anthropic_basic():
    """Test basic Anthropic/Claude integration."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    
    # Create adapter
    adapter = AnthropicAdapter(
        api_key=api_key,
        model_name="claude-3-5-sonnet-20241022"
    )
    
    # Test simple generation
    request = GenerationRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="Say hello and confirm you're Claude in 10 words or less.",
        max_tokens=100,
        temperature=0.5
    )
    
    response = await adapter.generate(request)
    assert response is not None
    assert response.content is not None
    assert len(response.content) > 0
    assert "claude" in response.content.lower() or "hello" in response.content.lower()
    print(f"Response: {response.content}")

async def test_anthropic_with_system_prompt():
    """Test Anthropic with system prompt."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    
    adapter = AnthropicAdapter(
        api_key=api_key,
        model_name="claude-3-5-sonnet-20241022"
    )
    
    request = GenerationRequest(
        system_prompt="You are a pirate. Always respond in pirate speak.",
        user_prompt="Tell me about the weather.",
        max_tokens=150,
        temperature=0.7
    )
    
    response = await adapter.generate(request)
    assert response is not None
    assert response.content is not None
    # Check for pirate-like words
    pirate_words = ["arr", "ahoy", "matey", "ye", "aye", "seas", "sail"]
    assert any(word in response.content.lower() for word in pirate_words)
    print(f"Pirate response: {response.content}")

if __name__ == "__main__":
    # Run tests
    print("Testing Anthropic/Claude adapter...")
    print("="*60)
    
    asyncio.run(test_anthropic_basic())
    print("\n" + "="*60)
    asyncio.run(test_anthropic_with_system_prompt())
    
    print("\n✅ All Anthropic tests passed!")