#!/usr/bin/env python3
"""List available Gemini models."""

import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure with a test API key (you'll need to provide one)
api_key = input("Enter your Google AI Studio API key: ").strip()
if not api_key:
    print("No API key provided. Exiting.")
    exit(1)

genai.configure(api_key=api_key)

print("\nAvailable models that support generateContent:")
print("-" * 50)

try:
    # List all available models
    for model in genai.list_models():
        # Check if model supports generateContent
        if 'generateContent' in model.supported_generation_methods:
            print(f"Model Name: {model.name}")
            print(f"Display Name: {model.display_name}")
            print(f"Description: {model.description}")
            print(f"Supported Methods: {', '.join(model.supported_generation_methods)}")
            print("-" * 50)
except Exception as e:
    print(f"Error listing models: {e}")
    print("\nTrying with hardcoded known model names...")
    
    # Try known model names
    known_models = [
        "gemini-pro",
        "gemini-1.0-pro", 
        "gemini-1.0-pro-latest",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-pro-001",
        "gemini-1.5-flash-001",
        "gemini-1.5-pro-002",
        "gemini-1.5-flash-002"
    ]
    
    print("\nTesting known model names:")
    for model_name in known_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Say 'test'")
            print(f"✓ {model_name} - WORKS")
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                print(f"✗ {model_name} - NOT FOUND")
            else:
                print(f"✗ {model_name} - ERROR: {error_msg[:100]}")