#!/usr/bin/env python3
"""Test script to inspect job model configuration in the database."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from setup_path import setup_test_paths
setup_test_paths()

import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Credential
from app.core.security import decrypt_credentials
from app.config import get_settings

def inspect_gemini_credentials():
    """Inspect Gemini credentials and their models."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all gemini credentials
        credentials = session.query(Credential).filter(
            Credential.type == "GEMINI"
        ).all()
        
        print(f"Found {len(credentials)} Gemini credentials")
        print("="*60)
        
        for cred in credentials:
            print(f"\nCredential: {cred.name}")
            print(f"  ID: {cred.id}")
            print(f"  Created: {cred.created_at}")
            
            # Decrypt to see the model
            try:
                decrypted = decrypt_credentials(cred.encrypted_data)
                model = decrypted.get("model", "Not specified")
                print(f"  Model: {model}")
            except Exception as e:
                print(f"  Error decrypting: {e}")
        
        # The "recent jobs using this credential" section is gone: a job no longer names
        # an AI credential. An instruction set names its agents and each agent names the AI
        # configuration it runs on, so the correlation now goes through agents.

        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        session.close()

def inspect_all_ai_credentials():
    """Inspect all AI credentials in the system."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all AI credentials
        ai_types = ["GEMINI", "ANTHROPIC", "OPENAI"]
        
        for ai_type in ai_types:
            credentials = session.query(Credential).filter(
                Credential.type == ai_type
            ).all()
            
            if credentials:
                print(f"\n{ai_type} Credentials ({len(credentials)}):")
                print("-" * 40)
                
                for cred in credentials:
                    print(f"  • {cred.name} (ID: {cred.id[:8]}...)")
                    
                    try:
                        decrypted = decrypt_credentials(cred.encrypted_data)
                        model = decrypted.get("model", "Not specified")
                        print(f"    Model: {model}")
                    except Exception as e:
                        print(f"    Error: {e}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    print("AI Credential Inspection")
    print("="*60)
    
    success = inspect_gemini_credentials()
    
    if success:
        print("\n" + "="*60)
        print("All AI Credentials Summary:")
        print("="*60)
        inspect_all_ai_credentials()
        
        print("\n✅ Inspection completed successfully!")
    else:
        print("\n❌ Inspection failed")