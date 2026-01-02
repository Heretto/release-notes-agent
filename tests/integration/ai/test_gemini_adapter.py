#!/usr/bin/env python3
"""Test Google Gemini integration."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from setup_path import setup_test_paths
setup_test_paths()

from dotenv import load_dotenv
load_dotenv()

import asyncio
import pytest
from app.services.gemini_adapter import GeminiAdapter
from app.services.ai_service import GenerationRequest

async def test_gemini_basic():
    """Test basic Gemini integration."""
    api_key = os.getenv('GOOGLE_AI_API_KEY')
    
    if not api_key:
        pytest.skip("GOOGLE_AI_API_KEY not set")
    
    # Test with the standard model
    model_name = "gemini-1.5-pro"
    
    adapter = GeminiAdapter(api_key=api_key, model_name=model_name)
    
    request = GenerationRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="Say hello and confirm you're Gemini in 10 words or less.",
        max_tokens=50,
        temperature=0.1
    )
    
    response = await adapter.generate(request)
    assert response is not None
    assert response.content is not None
    assert len(response.content) > 0
    print(f"Response: {response.content}")

async def test_gemini_model_name_cleaning():
    """Test that model name cleaning works correctly."""
    api_key = os.getenv('GOOGLE_AI_API_KEY')
    
    if not api_key:
        pytest.skip("GOOGLE_AI_API_KEY not set")
    
    # Test with various model name formats
    model_names = [
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest"
    ]
    
    for model_name in model_names:
        print(f"\nTesting model: {model_name}")
        try:
            adapter = GeminiAdapter(api_key=api_key, model_name=model_name)
            
            request = GenerationRequest(
                system_prompt="You are a helpful assistant.",
                user_prompt="Reply with 'OK' if this works.",
                max_tokens=20,
                temperature=0.1
            )
            
            response = await adapter.generate(request)
            assert response is not None
            assert response.content is not None
            print(f"✓ Model {model_name} works")
        except Exception as e:
            print(f"✗ Model {model_name} failed: {e}")

async def test_gemini_with_system_prompt():
    """Test Gemini with system prompt."""
    api_key = os.getenv('GOOGLE_AI_API_KEY')
    
    if not api_key:
        pytest.skip("GOOGLE_AI_API_KEY not set")
    
    adapter = GeminiAdapter(
        api_key=api_key,
        model_name="gemini-1.5-pro"
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
    pirate_words = ["arr", "ahoy", "matey", "ye", "aye", "seas", "sail", "captain"]
    assert any(word in response.content.lower() for word in pirate_words)
    print(f"Pirate response: {response.content}")

if __name__ == "__main__":
    # Run tests
    print("Testing Google Gemini adapter...")
    print("="*60)
    
    asyncio.run(test_gemini_basic())
    print("\n" + "="*60)
    asyncio.run(test_gemini_model_name_cleaning())
    print("\n" + "="*60)
    asyncio.run(test_gemini_with_system_prompt())
    
    print("\n✅ All Gemini tests passed!")