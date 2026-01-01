#!/usr/bin/env python3
"""Test script to list and verify available Gemini models."""

import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_models(api_key):
    """Test available Gemini models and their correct formatting."""
    
    genai.configure(api_key=api_key)
    
    print("\n" + "="*70)
    print("GEMINI MODEL VERIFICATION TEST")
    print("="*70)
    
    # Step 1: List all available models
    print("\n1. LISTING ALL AVAILABLE MODELS:")
    print("-"*50)
    
    available_models = []
    try:
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                print(f"\n✓ Model Name: {model.name}")
                print(f"  Display Name: {model.display_name}")
                print(f"  Description: {model.description[:100] if model.description else 'N/A'}...")
                available_models.append(model.name)
    except Exception as e:
        print(f"✗ Error listing models: {e}")
        return
    
    # Step 2: Test different model name formats
    print("\n\n2. TESTING MODEL NAME FORMATS:")
    print("-"*50)
    
    test_formats = [
        # Test the exact names from ListModels
        *available_models,
        # Test without 'models/' prefix
        *[name.replace('models/', '') for name in available_models if name.startswith('models/')],
        # Test common variations
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-pro",
        "models/gemini-1.5-pro",
        "models/gemini-1.5-flash",
        "models/gemini-pro",
        "gemini-1.5-pro-latest",
        "models/gemini-1.5-pro-latest",
        "gemini-1.0-pro",
        "models/gemini-1.0-pro",
    ]
    
    # Remove duplicates while preserving order
    test_formats = list(dict.fromkeys(test_formats))
    
    working_models = []
    
    for model_name in test_formats:
        try:
            print(f"\nTesting: '{model_name}'")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Return only the word 'test'")
            if response and response.text:
                print(f"  ✓ SUCCESS - Model works!")
                working_models.append(model_name)
            else:
                print(f"  ✗ FAILED - No response")
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                print(f"  ✗ NOT FOUND - Model doesn't exist")
            elif "not supported" in error_msg:
                print(f"  ✗ NOT SUPPORTED - Model exists but doesn't support generateContent")
            else:
                print(f"  ✗ ERROR - {error_msg[:100]}")
    
    # Step 3: Recommendations
    print("\n\n3. RECOMMENDATIONS:")
    print("-"*50)
    print("\nWorking model names that should be used:")
    for model in working_models:
        print(f"  • {model}")
    
    # Step 4: Check our current implementation
    print("\n\n4. CHECKING CURRENT IMPLEMENTATION:")
    print("-"*50)
    
    # Test what our adapter would produce
    test_cases = [
        "gemini-1.5-pro",
        "gemini-1.5-flash", 
        "gemini-pro"
    ]
    
    for test_name in test_cases:
        # Simulate our adapter logic
        if test_name in ["gemini-pro", "gemini-pro-vision"]:
            final_name = test_name
        elif not test_name.startswith("models/"):
            final_name = f"models/{test_name}"
        else:
            final_name = test_name
            
        print(f"\nInput: '{test_name}' -> Output: '{final_name}'")
        if final_name in working_models:
            print("  ✓ This will work!")
        else:
            print("  ✗ This will fail!")
    
    return working_models

def main():
    # Try to get API key from environment or prompt
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("\nNo API key found in environment variables.")
        print("Please enter your Google AI Studio API key")
        print("(Get one at https://makersuite.google.com/app/apikey)")
        api_key = input("\nAPI Key: ").strip()
    
    if not api_key:
        print("✗ No API key provided. Exiting.")
        sys.exit(1)
    
    # Run the test
    working_models = test_models(api_key)
    
    if working_models:
        print("\n\n" + "="*70)
        print("TEST COMPLETE")
        print(f"Found {len(working_models)} working model format(s)")
        print("="*70)
    else:
        print("\n\n✗ No working models found. Please check your API key.")

if __name__ == "__main__":
    main()