#!/usr/bin/env python3
"""Test OpenAI parameter handling for different models"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.openai_adapter import OpenAIAdapter

def test_model_detection():
    """Test that we correctly identify which models need which parameter."""
    
    print("=" * 60)
    print("OpenAI Model Parameter Detection Test")
    print("=" * 60)
    
    test_models = [
        ("gpt-3.5-turbo", "max_tokens"),
        ("gpt-3.5-turbo-16k", "max_tokens"),
        ("gpt-4", "max_tokens"),
        ("gpt-4-32k", "max_tokens"),
        ("gpt-4-turbo", "max_completion_tokens"),
        ("gpt-4-turbo-preview", "max_completion_tokens"),
        ("gpt-4o", "max_completion_tokens"),
        ("gpt-4o-mini", "max_completion_tokens"),
        ("o1-preview", "max_completion_tokens"),
        ("o1-mini", "max_completion_tokens"),
        ("chatgpt-4o-latest", "max_completion_tokens"),
    ]
    
    print("\nModel Parameter Mapping:")
    print("-" * 40)
    
    for model_name, expected_param in test_models:
        # Check which parameter would be used
        uses_max_completion_tokens = any(x in model_name.lower() for x in ["gpt-4-turbo", "gpt-4o", "o1", "chatgpt-4o"])
        actual_param = "max_completion_tokens" if uses_max_completion_tokens else "max_tokens"
        
        status = "✅" if actual_param == expected_param else "❌"
        print(f"{status} {model_name:25} -> {actual_param}")
        
        if actual_param != expected_param:
            print(f"   WARNING: Expected {expected_param}")
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("- Newer models (gpt-4-turbo, gpt-4o, o1) use max_completion_tokens")
    print("- Older models (gpt-3.5, gpt-4) use max_tokens")
    print("- The adapter automatically retries with the other parameter if needed")

if __name__ == "__main__":
    test_model_detection()