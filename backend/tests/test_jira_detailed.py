#!/usr/bin/env python3
"""Detailed test of Jira connection with full error information"""

import httpx
import asyncio
import base64
import sys
from pathlib import Path
import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import get_db, Credential, CredentialType
from app.core.security import decrypt_credentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

@pytest.mark.asyncio
async def test_jira_api():
    """Test Jira API with detailed error reporting."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as db:
        # Get valid Jira credential
        credentials = db.query(Credential).filter(
            Credential.type == CredentialType.JIRA
        ).all()
        
        credential = None
        for cred in credentials:
            try:
                decrypt_credentials(cred.encrypted_data)
                credential = cred
                break
            except:
                continue
        
        if not credential:
            print("❌ No valid Jira credentials found")
            return
        
        print(f"🔑 Using credential: {credential.name}")
        
        # Decrypt credentials
        cred_data = decrypt_credentials(credential.encrypted_data)
        server_url = cred_data['server_url'].rstrip('/')
        email = cred_data['email']
        api_token = cred_data['api_token']
        
        print(f"   Server: {server_url}")
        print(f"   Email: {email}")
        print(f"   Token: {api_token[:10]}..." if api_token else "No token")
        
        # Create auth header
        auth_str = f"{email}:{api_token}"
        auth_bytes = auth_str.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Test 1: Basic connection test
        print("\n📡 Test 1: Testing /myself endpoint...")
        test_url = f"{server_url}/rest/api/3/myself"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(test_url, headers=headers)
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    user_data = response.json()
                    print(f"   ✅ Connected as: {user_data.get('displayName', 'Unknown')}")
                else:
                    print(f"   ❌ Failed: {response.text[:200]}")
                    
        except httpx.ConnectError as e:
            print(f"   ❌ Connection error: {e}")
            print(f"   Error details: {str(e.args)}")
        except httpx.TimeoutException as e:
            print(f"   ❌ Timeout error: {e}")
        except Exception as e:
            print(f"   ❌ Unexpected error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 2: Search endpoint with POST
        print("\n🔍 Test 2: Testing search endpoint...")
        search_url = f"{server_url}/rest/api/3/search/jql"
        search_body = {
            "jql": "created >= -30d order by created desc",
            "maxResults": 5,
            "fields": ["summary", "status", "created", "key"]
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    search_url, 
                    headers=headers, 
                    json=search_body
                )
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ Search successful: {data.get('total', 0)} issues found")
                else:
                    print(f"   ❌ Failed: {response.text[:200]}")
                    
        except httpx.ConnectError as e:
            print(f"   ❌ Connection error: {e}")
            print(f"   Full error: {e.__class__.__module__}.{e.__class__.__name__}")
            if hasattr(e, '__cause__'):
                print(f"   Caused by: {e.__cause__}")
        except Exception as e:
            print(f"   ❌ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Detailed Jira API Test")
    print("=" * 60)
    asyncio.run(test_jira_api())