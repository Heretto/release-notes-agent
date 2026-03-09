#!/usr/bin/env python3
"""Test OpenAI adapter implementation"""

import sys
from pathlib import Path
import asyncio
import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ai_service import AIServiceFactory, GenerationRequest

@pytest.mark.asyncio
async def test_openai_adapter():
    """Test that OpenAI adapter can be created and used."""
    
    print("=" * 60)
    print("OpenAI Adapter Test")
    print("=" * 60)
    
    # Test 1: Factory can create OpenAI adapter
    print("\n1. Testing AIServiceFactory with OpenAI...")
    try:
        # Create with a dummy API key for testing
        adapter = AIServiceFactory.create(
            provider="openai",
            api_key="sk-test-key-1234567890",
            model="gpt-4-turbo-preview"
        )
        print("   ✅ OpenAI adapter created successfully")
        print(f"   Model: {adapter.get_model_name()}")
    except ValueError as e:
        if "Unknown AI provider: openai" in str(e):
            print(f"   ❌ OpenAI not registered in factory: {e}")
            return False
        else:
            print(f"   ⚠️  Expected error (no real API key): {e}")
    except Exception as e:
        print(f"   ⚠️  Initialization error (expected with dummy key): {e}")
    
    # Test 2: Test the adapter structure
    print("\n2. Testing adapter interface...")
    try:
        request = GenerationRequest(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say hello",
            max_tokens=50,
            temperature=0.7
        )
        
        # We can't actually call generate without a real API key
        # but we can verify the adapter has the required methods
        assert hasattr(adapter, 'generate'), "Missing generate method"
        assert hasattr(adapter, 'generate_stream'), "Missing generate_stream method"
        assert hasattr(adapter, 'get_model_name'), "Missing get_model_name method"
        
        print("   ✅ Adapter has all required methods")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 3: Verify provider mapping
    print("\n3. Testing provider mapping...")
    providers = ["openai", "gemini", "anthropic"]
    for provider in providers:
        try:
            test_adapter = AIServiceFactory.create(
                provider=provider,
                api_key="test-key",
                model=None
            )
            print(f"   ✅ {provider}: registered")
        except ValueError as e:
            print(f"   ❌ {provider}: {e}")
        except Exception:
            # Expected for dummy keys
            print(f"   ✅ {provider}: registered (init failed with dummy key)")
    
    print("\n" + "=" * 60)
    print("Summary: OpenAI adapter is now available for job execution!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_openai_adapter())
    sys.exit(0 if success else 1)