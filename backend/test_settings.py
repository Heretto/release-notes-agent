#!/usr/bin/env python3
"""Test settings loading."""

from pydantic_settings import BaseSettings

# Test 1: Default class
class TestSettings1(BaseSettings):
    google_ai_model: str = "gemini-1.5-pro-latest"

s1 = TestSettings1()
print(f"Test 1 (new class): google_ai_model = {s1.google_ai_model}")

# Test 2: Import actual Settings
from app.config import Settings
s2 = Settings()
print(f"Test 2 (Settings): google_ai_model = {s2.google_ai_model}")

# Test 3: Check what the file actually says
with open('/app/app/config.py', 'r') as f:
    for line in f:
        if 'google_ai_model' in line:
            print(f"File content: {line.strip()}")

# Test 4: Check if there's a .env overriding it
import os
env_val = os.getenv('GOOGLE_AI_MODEL')
print(f"Environment GOOGLE_AI_MODEL: {env_val}")
env_val2 = os.getenv('google_ai_model')  
print(f"Environment google_ai_model: {env_val2}")