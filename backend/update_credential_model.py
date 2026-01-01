#!/usr/bin/env python3
"""Update existing Gemini credentials to use valid model names."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Credential
from app.core.security import decrypt_credentials, encrypt_credentials
from app.config import Settings

def update_credentials():
    settings = Settings()
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all Gemini credentials
        credentials = session.query(Credential).filter(
            Credential.type == "GEMINI"
        ).all()
        
        print(f"Found {len(credentials)} Gemini credential(s) to update")
        
        for cred in credentials:
            print(f"\nUpdating credential: {cred.name}")
            
            # Decrypt current data
            decrypted = decrypt_credentials(cred.encrypted_data)
            old_model = decrypted.get("model", "")
            
            print(f"  Current model: {old_model}")
            
            # Update invalid model names to valid ones
            model_mapping = {
                "gemini-1.5-pro-latest": "gemini-2.5-pro",
                "gemini-1.5-pro": "gemini-2.5-pro",
                "gemini-1.5-flash-latest": "gemini-2.5-flash",
                "gemini-1.5-flash": "gemini-2.5-flash",
                "gemini-1.0-pro-latest": "gemini-pro-latest",
                "gemini-1.0-pro": "gemini-pro-latest",
                "": "gemini-2.5-pro"  # Default for empty
            }
            
            new_model = model_mapping.get(old_model, old_model)
            
            if new_model != old_model:
                print(f"  Updating to: {new_model}")
                decrypted["model"] = new_model
                
                # Re-encrypt and save
                cred.encrypted_data = encrypt_credentials(decrypted)
                session.commit()
                print(f"  ✓ Updated successfully")
            else:
                print(f"  Model is already valid, no update needed")
        
        print("\nAll credentials updated successfully")
        
    except Exception as e:
        print(f"Error updating credentials: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    update_credentials()