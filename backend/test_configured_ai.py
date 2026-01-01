#!/usr/bin/env python3
"""Test AI credentials from database configuration."""

import asyncio
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Credential
from app.core.security import decrypt_credentials
from app.services.ai_service import AIServiceFactory, GenerationRequest
from app.config import Settings

async def test_configured_credentials():
    settings = Settings()
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all AI credentials
        credentials = session.query(Credential).filter(
            Credential.type.in_(["GEMINI", "OPENAI", "ANTHROPIC"])
        ).all()
        
        if not credentials:
            print("No AI credentials found in database")
            return
        
        print(f"Found {len(credentials)} AI credential(s)")
        print("=" * 80)
        
        for cred in credentials:
            print(f"\nTesting credential: {cred.name} (Type: {cred.type})")
            print("-" * 60)
            
            # Decrypt credentials
            decrypted = decrypt_credentials(cred.encrypted_data)
            api_key = decrypted.get("api_key", "")
            model = decrypted.get("model", "")
            
            print(f"  Provider: {cred.type.value.lower()}")
            print(f"  Model: {model or 'default'}")
            print(f"  API Key: ...{api_key[-4:] if len(api_key) > 4 else '***'}")
            
            try:
                # Create AI service using the exact same logic as the job orchestrator
                print(f"\n  Creating AI service...")
                ai_service = AIServiceFactory.create(
                    provider=cred.type.value.lower(),
                    api_key=api_key,
                    model=model
                )
                
                print(f"  ✓ AI service created successfully")
                print(f"  Model name from service: {ai_service.get_model_name()}")
                
                # Create a simple test request
                test_request = GenerationRequest(
                    system_prompt="You are a helpful assistant.",
                    user_prompt="Respond with exactly: 'Test successful'",
                    max_tokens=20,
                    temperature=0.1
                )
                
                print(f"\n  Sending test request...")
                print(f"    System prompt: {test_request.system_prompt}")
                print(f"    User prompt: {test_request.user_prompt}")
                print(f"    Max tokens: {test_request.max_tokens}")
                print(f"    Temperature: {test_request.temperature}")
                
                # Try to generate
                response = await ai_service.generate(test_request)
                
                print(f"\n  ✓ SUCCESS!")
                print(f"    Response: {response.content}")
                print(f"    Model used: {response.model}")
                print(f"    Finish reason: {response.finish_reason}")
                
            except Exception as e:
                print(f"\n  ✗ FAILED!")
                print(f"    Error type: {type(e).__name__}")
                print(f"    Error message: {str(e)}")
                
                # Try to extract more details
                if hasattr(e, '__dict__'):
                    print(f"    Error details: {e.__dict__}")
                
                # Show the full traceback for debugging
                import traceback
                print(f"\n  Full traceback:")
                traceback.print_exc()
        
    finally:
        session.close()
    
    print("\n" + "=" * 80)
    print("Test complete")

if __name__ == "__main__":
    asyncio.run(test_configured_credentials())