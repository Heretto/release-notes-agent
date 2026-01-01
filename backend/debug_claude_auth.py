#!/usr/bin/env python3
"""Debug Claude authentication issues."""

import os
import sys
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Credential
from app.core.security import decrypt_credentials
from app.config import Settings
import anthropic

def debug_stored_credentials():
    """Check what's stored in the database for Anthropic credentials."""
    settings = Settings()
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all Anthropic credentials
        credentials = session.query(Credential).filter(
            Credential.type == "ANTHROPIC"
        ).all()
        
        print(f"Found {len(credentials)} Anthropic credential(s)")
        
        for cred in credentials:
            print(f"\n=== Credential: {cred.name} ===")
            print(f"ID: {cred.id}")
            print(f"Type: {cred.type}")
            
            # Decrypt and check the stored data
            decrypted = decrypt_credentials(cred.encrypted_data)
            api_key = decrypted.get("api_key", "")
            model = decrypted.get("model", "")
            
            print(f"Stored API key length: {len(api_key)}")
            print(f"Stored API key format: {api_key[:10]}...{api_key[-5:] if len(api_key) > 15 else ''}")
            print(f"Starts with 'sk-': {api_key.startswith('sk-')}")
            print(f"Contains whitespace: {api_key != api_key.strip()}")
            print(f"Model: {model}")
            
            # Test the API key directly
            print("\nTesting API key with Anthropic...")
            try:
                client = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Say 'test'"}]
                )
                print("✅ API key works!")
            except anthropic.AuthenticationError as e:
                print(f"❌ Authentication failed: {e}")
            except Exception as e:
                print(f"❌ Other error: {e}")
            
    except Exception as e:
        print(f"Error reading credentials: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    debug_stored_credentials()