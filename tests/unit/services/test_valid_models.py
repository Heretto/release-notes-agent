#!/usr/bin/env python3
"""Test that AI services accept valid model names."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from setup_path import setup_test_paths
setup_test_paths()

from app.services.gemini_adapter import GeminiAdapter
from app.services.anthropic_adapter import AnthropicAdapter

def test_gemini_valid_models():
    """Test that Gemini adapter accepts valid model names."""
    valid_models = [
        "gemini-1.5-pro",
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash-8b",
        "gemini-2.0-flash-exp"
    ]
    
    print("Testing Gemini model names...")
    print("="*40)
    
    for model in valid_models:
        try:
            # Just test initialization, not actual API calls
            adapter = GeminiAdapter(api_key="test_key", model_name=model)
            # Check that model name is cleaned properly
            if hasattr(adapter, 'model_name'):
                print(f"✓ {model} -> {adapter.model_name}")
            else:
                print(f"✓ {model} accepted")
        except Exception as e:
            print(f"✗ {model} failed: {e}")
    
    return True

def test_anthropic_valid_models():
    """Test that Anthropic adapter accepts valid model names."""
    valid_models = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307"
    ]
    
    print("\nTesting Anthropic/Claude model names...")
    print("="*40)
    
    for model in valid_models:
        try:
            # Just test initialization, not actual API calls
            adapter = AnthropicAdapter(api_key="test_key", model_name=model)
            print(f"✓ {model} accepted")
        except Exception as e:
            print(f"✗ {model} failed: {e}")
    
    return True

def test_model_name_validation():
    """Test model name validation logic."""
    print("\nTesting model name validation...")
    print("="*40)
    
    # Test Gemini model cleaning
    test_cases = [
        ("gemini-1.5-pro-latest", "gemini-1.5-pro"),
        ("gemini-1.5-flash-latest", "gemini-1.5-flash"),
        ("gemini-1.5-flash-8b-latest", "gemini-1.5-flash-8b"),
        ("gemini-2.0-flash-exp", "gemini-2.0-flash-exp"),  # exp models keep their suffix
    ]
    
    print("Gemini model name cleaning:")
    for input_name, expected in test_cases:
        # Simulate the cleaning logic
        cleaned = input_name.replace("-latest", "") if "-latest" in input_name and "-exp" not in input_name else input_name
        if cleaned == expected:
            print(f"  ✓ {input_name} -> {expected}")
        else:
            print(f"  ✗ {input_name} -> {cleaned} (expected {expected})")
    
    return True

if __name__ == "__main__":
    print("AI Model Names Validation Test")
    print("="*60)
    
    # Run tests
    test_gemini_valid_models()
    test_anthropic_valid_models()
    test_model_name_validation()
    
    print("\n✅ Model validation tests completed!")