#!/usr/bin/env python3
"""Test which Claude models actually work."""

import anthropic
import os

# Common model names to test based on Anthropic's documentation
models_to_test = [
    # Claude 3.5 models
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-20241022",
    "claude-3-5-haiku-latest",
    
    # Claude 3 Opus
    "claude-3-opus-20240229",
    "claude-3-opus-latest",
    
    # Claude 3 Sonnet
    "claude-3-sonnet-20240229",
    "claude-3-sonnet-latest",
    
    # Claude 3 Haiku
    "claude-3-haiku-20240307",
    "claude-3-haiku-latest",
    
    # Claude 2
    "claude-2.1",
    "claude-2.0",
    
    # Claude Instant
    "claude-instant-1.2",
    
    # Try without version specifiers
    "claude-3-opus",
    "claude-3-sonnet",
    "claude-3-haiku",
    "claude-3-5-sonnet",
    "claude-3-5-haiku",
]

def test_model(client, model_name):
    """Test if a model name works."""
    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        return True
    except anthropic.NotFoundError:
        return False
    except Exception as e:
        print(f"  Unexpected error for {model_name}: {e}")
        return False

if __name__ == "__main__":
    api_key = input("Enter your Anthropic API key: ").strip()
    
    if not api_key or api_key == "your-api-key-here":
        print("Please provide a valid API key")
        exit(1)
    
    client = anthropic.Anthropic(api_key=api_key)
    
    print("\nTesting Claude models...\n")
    print("=" * 50)
    
    working_models = []
    
    for model in models_to_test:
        works = test_model(client, model)
        status = "✅ WORKS" if works else "❌ NOT FOUND"
        print(f"{status}: {model}")
        if works:
            working_models.append(model)
    
    print("\n" + "=" * 50)
    print(f"\nWorking models ({len(working_models)}):")
    for model in working_models:
        print(f"  - {model}")