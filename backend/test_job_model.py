#!/usr/bin/env python3
"""Test script to see what model is being used for jobs."""

import os
import sys
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Credential
from app.core.security import decrypt_credentials
from app.config import Settings

settings = Settings()
engine = create_engine(settings.database_url)
Session = sessionmaker(bind=engine)
session = Session()

try:
    # Get all gemini credentials
    credentials = session.query(Credential).filter(
        Credential.type == "gemini"
    ).all()
    
    print(f"Found {len(credentials)} Gemini credentials")
    print("="*60)
    
    for cred in credentials:
        print(f"\nCredential: {cred.name}")
        print(f"  ID: {cred.id}")
        print(f"  Created: {cred.created_at}")
        
        # Decrypt and check the model
        decrypted = decrypt_credentials(cred.encrypted_data)
        print(f"  Stored data:")
        for key, value in decrypted.items():
            if key != "api_key":
                print(f"    {key}: {value}")
            else:
                print(f"    api_key: ***{value[-4:] if len(value) > 4 else '***'}")
        
        # Check what model would be used
        model = decrypted.get("model", settings.google_ai_model)
        print(f"  Model that will be used: {model}")
        
        if "model" not in decrypted or decrypted["model"] == "":
            print(f"  --> Will use default: {settings.google_ai_model}")
        
finally:
    session.close()