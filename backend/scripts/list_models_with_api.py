#!/usr/bin/env python3
"""List available Gemini models using the configured API key."""

import google.generativeai as genai
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Credential
from app.core.security import decrypt_credentials
from app.config import Settings

def list_models():
    settings = Settings()
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get Gemini credential
        cred = session.query(Credential).filter(
            Credential.type == "GEMINI"
        ).first()
        
        if not cred:
            print("No Gemini credential found")
            return
        
        # Decrypt and get API key
        decrypted = decrypt_credentials(cred.encrypted_data)
        api_key = decrypted.get("api_key", "")
        
        print(f"Using API key ending in: ...{api_key[-4:]}")
        
        # Configure the SDK
        genai.configure(api_key=api_key)
        
        print("\nListing all available models:")
        print("=" * 80)
        
        # List all models
        for model in genai.list_models():
            print(f"\nModel Name: {model.name}")
            print(f"  Display Name: {model.display_name}")
            print(f"  Description: {model.description[:100] if model.description else 'N/A'}...")
            print(f"  Supported Methods: {model.supported_generation_methods}")
            
            # Check if this model supports generateContent
            if 'generateContent' in model.supported_generation_methods:
                print(f"  ✓ Supports generateContent")
                
                # Test if we can create a GenerativeModel with this name
                try:
                    # Try with the full name as returned
                    test_model = genai.GenerativeModel(model.name)
                    print(f"  ✓ Can create GenerativeModel with: {model.name}")
                except Exception as e:
                    print(f"  ✗ Cannot create with full name: {e}")
                
                # Try without "models/" prefix if present
                if model.name.startswith("models/"):
                    short_name = model.name[7:]
                    try:
                        test_model = genai.GenerativeModel(short_name)
                        print(f"  ✓ Can create GenerativeModel with: {short_name}")
                    except Exception as e:
                        print(f"  ✗ Cannot create with short name: {e}")
        
        print("\n" + "=" * 80)
        print("\nRecommendations:")
        print("-" * 40)
        print("Based on the model listing above, use the exact model name format")
        print("that shows '✓ Can create GenerativeModel with:' for your configuration.")
        
    finally:
        session.close()

if __name__ == "__main__":
    list_models()