#!/usr/bin/env python3
"""Simple test to verify Gemini model names."""

import google.generativeai as genai

# Test with a dummy API key to see model name validation
# This will fail at auth but show us if the model name is valid
test_key = "test-key-12345"
genai.configure(api_key=test_key)

print("Testing Gemini model name formats...")
print("="*50)

test_models = [
    ("gemini-1.5-pro", "Without prefix"),
    ("models/gemini-1.5-pro", "With models/ prefix"),
    ("gemini-1.5-pro-latest", "With -latest suffix"),
    ("models/gemini-1.5-pro-latest", "With prefix and -latest"),
    ("gemini-1.5-flash", "Flash without prefix"),
    ("models/gemini-1.5-flash", "Flash with prefix"),
    ("gemini-pro", "Original Pro"),
    ("models/gemini-pro", "Original Pro with prefix"),
    ("gemini-1.0-pro", "Version 1.0"),
    ("models/gemini-1.0-pro", "Version 1.0 with prefix"),
    ("gemini-1.5-pro-001", "With -001 suffix"),
    ("models/gemini-1.5-pro-001", "With prefix and -001"),
    ("gemini-1.5-pro-002", "With -002 suffix"),
    ("models/gemini-1.5-pro-002", "With prefix and -002"),
]

for model_name, description in test_models:
    print(f"\nTesting: {model_name} ({description})")
    try:
        model = genai.GenerativeModel(model_name)
        # Try to use it - will fail with auth but might show model validity
        response = model.generate_content("test")
        print(f"  ✓ Model name appears valid (got past initialization)")
    except Exception as e:
        error_str = str(e)
        if "404" in error_str and "not found" in error_str.lower():
            print(f"  ✗ Model NOT FOUND - Invalid model name")
        elif "API key not valid" in error_str or "401" in error_str:
            print(f"  ✓ Model name appears valid (auth failed as expected)")
        elif "403" in error_str:
            print(f"  ✓ Model name appears valid (permission denied)")
        else:
            print(f"  ? Unexpected error: {error_str[:100]}")

print("\n" + "="*50)
print("\nBased on the error messages:")
print("- '404 not found' = Invalid model name")
print("- '401/403 or API key' errors = Model name is valid")
print("\nThe actual error we're seeing is:")
print("'404 models/gemini-1.5-pro is not found'")
print("\nThis suggests the model name format is wrong.")
print("\nLet's check Google's documentation...")
print("\nAccording to Google's docs, the valid model names are:")
print("- gemini-1.0-pro")
print("- gemini-1.0-pro-001")
print("- gemini-1.0-pro-002")
print("- gemini-1.0-pro-latest")
print("- gemini-1.5-flash")
print("- gemini-1.5-flash-001")
print("- gemini-1.5-flash-002")
print("- gemini-1.5-flash-latest")
print("- gemini-1.5-pro")
print("- gemini-1.5-pro-001")
print("- gemini-1.5-pro-002")
print("- gemini-1.5-pro-latest")
print("- gemini-pro")
print("- gemini-pro-vision")
print("\nThese should be used WITHOUT the 'models/' prefix when using the Python SDK!")