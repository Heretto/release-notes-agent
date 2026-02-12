#!/usr/bin/env python3
"""
List valid credentials and identify which ones can be decrypted
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import get_db, Credential, CredentialType
from app.core.security import decrypt_credentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

def list_credentials():
    """List all credentials and check which can be decrypted."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as db:
        # Get all Jira credentials
        credentials = db.query(Credential).filter(
            Credential.type == CredentialType.JIRA
        ).all()
        
        print(f"Found {len(credentials)} Jira credential(s):\n")
        
        valid_count = 0
        for cred in credentials:
            print(f"ID: {cred.id}")
            print(f"Name: {cred.name}")
            print(f"Created by: {cred.created_by}")
            print(f"Organization ID: {cred.organization_id}")
            
            try:
                # Try to decrypt
                data = decrypt_credentials(cred.encrypted_data)
                print(f"✅ Can decrypt - Server: {data['server_url']}")
                valid_count += 1
            except Exception as e:
                print(f"❌ Cannot decrypt - {e.__class__.__name__}")
            
            print("-" * 50)
        
        print(f"\nSummary: {valid_count}/{len(credentials)} credentials can be decrypted")
        
        if valid_count == 0:
            print("\n⚠️  No valid Jira credentials found.")
            print("Please add new Jira credentials through the web interface.")

if __name__ == "__main__":
    list_credentials()