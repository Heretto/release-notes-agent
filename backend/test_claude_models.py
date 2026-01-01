#!/usr/bin/env python3
"""Test which Claude models are available."""

import anthropic
import os

# Test with these model names
models_to_test = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022", 
    "claude-3-opus-20240229",
    "claude-3-opus-latest",
    "claude-3-sonnet-20240229",
    "claude-3-sonnet-latest",
    "claude-3-haiku-20240307",
    "claude-3-haiku-latest",
    "claude-2.1",
    "claude-instant-1.2"
]

api_key = os.environ.get("ANTHROPIC_API_KEY", "your-api-key-here")
if api_key == "your-api-key-here":
    print("Please set ANTHROPIC_API_KEY environment variable")
    exit(1)

client = anthropic.Anthropic(api_key=api_key)

print("Testing Claude model availability:\n")

for model in models_to_test:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'ok'"}]
        )
        print(f"✓ {model} - Available")
    except anthropic.NotFoundError as e:
        print(f"✗ {model} - Not found")
    except Exception as e:
        print(f"? {model} - Error: {str(e)[:50]}")

print("\nNote: Models marked with ✓ are available for use.")