#!/usr/bin/env python3
"""Test Anthropic models with 2024 API."""

import anthropic
import sys

# Based on latest Anthropic docs (Dec 2024)
# These are the currently available models
models_to_try = [
    # Claude 3.5 Sonnet (newest)
    "claude-3-5-sonnet-20241022",
    
    # Claude 3.5 Haiku
    "claude-3-5-haiku-20241022",
    
    # Claude 3 Opus
    "claude-3-opus-20240229",
    
    # Claude 3 Sonnet  
    "claude-3-sonnet-20240229",
    
    # Claude 3 Haiku
    "claude-3-haiku-20240307",
]

if len(sys.argv) < 2:
    print("Usage: python test_anthropic_2024.py YOUR_API_KEY")
    sys.exit(1)

api_key = sys.argv[1].strip()
print(f"Testing with API key format: {api_key[:15]}...")
print(f"API key length: {len(api_key)}")

# Check API key format
if not api_key.startswith("sk-ant-"):
    print("⚠️  Warning: API key should start with 'sk-ant-'")

try:
    client = anthropic.Anthropic(api_key=api_key)
    
    # First, let's try a simple test with the recommended model
    print("\nTesting Claude 3.5 Sonnet (recommended)...")
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": "Say 'Hello! I am Claude and I'm working!' in exactly those words."
            }
        ]
    )
    
    print("✅ SUCCESS!")
    print(f"Response: {response.content[0].text}")
    print(f"\nModel 'claude-3-5-sonnet-20241022' is working with your API key!")
    
except anthropic.NotFoundError as e:
    print(f"❌ Model not found: {e}")
    print("\nTrying other models...")
    
    # Try other models
    client = anthropic.Anthropic(api_key=api_key)
    for model in models_to_try[1:]:  # Skip the first one we already tried
        try:
            print(f"  Testing {model}...", end=" ")
            response = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            print(f"✅ WORKS!")
            break
        except:
            print(f"❌ Not available")
    
except anthropic.AuthenticationError as e:
    print(f"❌ Authentication error: {e}")
    print("\nYour API key is invalid. Please:")
    print("1. Go to https://console.anthropic.com/settings/keys")
    print("2. Create a new API key")
    print("3. Make sure to copy the ENTIRE key")
    print("4. The key should start with 'sk-ant-api03-' and be over 100 characters")
    
except anthropic.PermissionDeniedError as e:
    print(f"❌ Permission denied: {e}")
    print("\nYour API key is valid but doesn't have access to Claude models.")
    print("Check your Anthropic account permissions.")
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    print(f"Error type: {type(e)}")