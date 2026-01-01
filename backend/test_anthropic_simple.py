#!/usr/bin/env python3
"""Simple test to find working Anthropic models."""

import anthropic
import sys

# These are the most commonly available models
models_to_try = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022", 
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "claude-3-opus-20240229",
    "claude-2.1",
    "claude-2.0",
    "claude-instant-1.2",
    "claude-instant-1",
]

if len(sys.argv) < 2:
    print("Usage: python test_anthropic_simple.py YOUR_API_KEY")
    sys.exit(1)

api_key = sys.argv[1].strip()
print(f"Testing with API key: {api_key[:10]}...{api_key[-5:]}")
print(f"API key length: {len(api_key)}")

client = anthropic.Anthropic(api_key=api_key)

print("\nTrying different model names:\n")

for model in models_to_try:
    try:
        print(f"Testing {model}...", end=" ")
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"✅ SUCCESS!")
        print(f"  Response: {response.content[0].text if response.content else 'No content'}")
        print(f"  THIS MODEL WORKS: {model}\n")
        break  # Stop after finding the first working model
    except anthropic.NotFoundError as e:
        print(f"❌ Not found")
    except anthropic.AuthenticationError as e:
        print(f"❌ Auth error: {e}")
        print("\nYour API key appears to be invalid. Please check it.")
        break
    except Exception as e:
        print(f"❌ Error: {e}")

print("\nIf no models worked, please verify:")
print("1. Your API key is correct and complete")
print("2. Your API key starts with 'sk-ant-api'")
print("3. You have access to Claude models in your Anthropic account")