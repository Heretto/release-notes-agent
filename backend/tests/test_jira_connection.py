#!/usr/bin/env python3
"""
Test Jira connection and search functionality
"""
import asyncio
import sys
from pathlib import Path
import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.jira_service_v3 import JiraServiceV3
from app.models.database import get_db, Credential, CredentialType
from app.core.security import decrypt_credentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

@pytest.mark.asyncio
async def test_jira_connection():
    """Test Jira connection and search."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as db:
        # Get a valid Jira credential (one that can be decrypted)
        credentials = db.query(Credential).filter(
            Credential.type == CredentialType.JIRA
        ).all()
        
        credential = None
        for cred in credentials:
            try:
                # Try to decrypt to find a valid one
                decrypt_credentials(cred.encrypted_data)
                credential = cred
                break
            except:
                continue
        
        if not credential:
            print("❌ No Jira credentials found in database")
            return
        
        print(f"📝 Testing with credential: {credential.name}")
        
        try:
            # Decrypt credentials
            cred_data = decrypt_credentials(credential.encrypted_data)
            print(f"   Server: {cred_data['server_url']}")
            print(f"   Email: {cred_data['email']}")
            
            # Create Jira service
            jira = JiraServiceV3(
                server=cred_data['server_url'],
                email=cred_data['email'],
                api_token=cred_data['api_token']
            )
            
            # Test connection
            print("\n🔌 Testing connection...")
            result = await jira.test_connection()
            if result['success']:
                print(f"   ✅ Connected as: {result['user']['displayName']}")
                print(f"   Email: {result['user']['emailAddress']}")
            else:
                print(f"   ❌ Connection failed: {result['message']}")
                return
            
            # Test search with simple query
            print("\n🔍 Testing search...")
            try:
                # Try a bounded query (last 30 days)
                tickets = await jira.execute_query(
                    jql="created >= -30d order by created desc",
                    max_results=5
                )
                
                print(f"   ✅ Search successful! Found {len(tickets)} tickets")
                
                if tickets:
                    print("\n   Recent tickets:")
                    for ticket in tickets[:3]:
                        print(f"   • {ticket.key}: {ticket.summary[:60]}...")
                        print(f"     Status: {ticket.status}, Type: {ticket.issue_type}")
                else:
                    print("   ℹ️ No tickets found (this might be normal if the Jira instance is empty)")
                    
                # Try to get total count
                if hasattr(jira, 'last_query_total'):
                    print(f"\n   Total accessible tickets: {jira.last_query_total}")
                    
            except Exception as search_error:
                print(f"   ❌ Search failed: {search_error}")
                
                # Try alternative queries
                print("\n   Trying alternative queries...")
                
                # Try searching in a specific project if we can get projects
                try:
                    projects = await jira.get_projects()
                    if projects:
                        print(f"   Found {len(projects)} accessible projects:")
                        for proj in projects[:3]:
                            print(f"   • {proj['key']}: {proj['name']}")
                        
                        # Try searching in the first project
                        first_project = projects[0]['key']
                        print(f"\n   Trying to search in project {first_project}...")
                        tickets = await jira.execute_query(
                            jql=f"project = {first_project} order by created desc",
                            max_results=5
                        )
                        print(f"   ✅ Found {len(tickets)} tickets in {first_project}")
                except Exception as proj_error:
                    print(f"   ❌ Could not get projects: {proj_error}")
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_jira_connection())