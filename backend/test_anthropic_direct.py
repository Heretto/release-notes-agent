#!/usr/bin/env python3
"""Direct test of Anthropic API key."""

import sys
import anthropic

def test_api_key(api_key):
    """Test if the API key works."""
    print(f"Testing API key: {api_key[:10]}...{api_key[-5:]}")
    print(f"API key length: {len(api_key)}")
    print(f"API key starts with 'sk-': {api_key.startswith('sk-')}")
    
    # Strip any whitespace
    api_key = api_key.strip()
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'test'"}]
        )
        print("✅ SUCCESS! API key is valid.")
        print(f"Response: {response.content[0].text if response.content else 'No content'}")
        return True
    except anthropic.AuthenticationError as e:
        print(f"❌ AUTHENTICATION ERROR: {e}")
        return False
    except Exception as e:
        print(f"❌ OTHER ERROR: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_anthropic_direct.py YOUR_API_KEY")
        sys.exit(1)
    
    api_key = sys.argv[1]
    test_api_key(api_key)