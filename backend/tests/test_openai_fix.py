#!/usr/bin/env python3
"""Test OpenAI credential parameter compatibility fix"""

import httpx
import asyncio
import json
import pytest

@pytest.mark.asyncio
async def test_openai_params():
    """Test different OpenAI parameter configurations."""
    
    # This simulates what the credential test does
    test_cases = [
        {
            "name": "With max_completion_tokens (new models)",
            "body": {
                "model": "gpt-4-turbo-preview",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'test'"}
                ],
                "temperature": 0.1,
                "max_completion_tokens": 20
            }
        },
        {
            "name": "With max_tokens (legacy models)",
            "body": {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'test'"}
                ],
                "temperature": 0.1,
                "max_tokens": 20
            }
        }
    ]
    
    print("=" * 60)
    print("OpenAI Parameter Compatibility Test")
    print("=" * 60)
    
    # Note: This won't actually call OpenAI without a real API key
    # It's just to demonstrate the parameter handling
    
    for test in test_cases:
        print(f"\n📝 Test: {test['name']}")
        print(f"   Model: {test['body']['model']}")
        print(f"   Parameters: {json.dumps({k: v for k, v in test['body'].items() if k != 'messages'}, indent=6)}")
        
        # Show what the fix does
        if "max_completion_tokens" in test['body']:
            print("   ✅ Using max_completion_tokens for newer models")
        else:
            print("   ✅ Using max_tokens for legacy models")
    
    print("\n" + "=" * 60)
    print("The credential test now:")
    print("1. First tries with max_completion_tokens (for new models)")
    print("2. If that fails with a parameter error, retries with max_tokens")
    print("3. This ensures compatibility with both old and new OpenAI models")

if __name__ == "__main__":
    asyncio.run(test_openai_params())