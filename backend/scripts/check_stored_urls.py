#!/usr/bin/env python3
"""Check the exact URLs stored in credentials"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import get_db, Credential, CredentialType
from app.core.security import decrypt_credentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
import urllib.parse

def check_urls():
    """Check all stored Jira URLs for issues."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as db:
        credentials = db.query(Credential).filter(
            Credential.type == CredentialType.JIRA
        ).all()
        
        print(f"Found {len(credentials)} Jira credential(s)\n")
        
        for cred in credentials:
            print(f"📋 Credential: {cred.name}")
            print(f"   ID: {cred.id}")
            
            try:
                data = decrypt_credentials(cred.encrypted_data)
                url = data.get('server_url', '')
                
                print(f"   Raw URL: '{url}'")
                print(f"   URL length: {len(url)}")
                print(f"   URL bytes: {url.encode('utf-8')}")
                
                # Check for common issues
                issues = []
                
                if url != url.strip():
                    issues.append("Has leading/trailing whitespace")
                
                if ' ' in url:
                    issues.append("Contains spaces")
                    
                if '\n' in url or '\r' in url or '\t' in url:
                    issues.append("Contains newlines or tabs")
                
                if not url.startswith('http://') and not url.startswith('https://'):
                    issues.append("Missing http:// or https:// prefix")
                
                # Try to parse the URL
                try:
                    parsed = urllib.parse.urlparse(url)
                    print(f"   Parsed - Scheme: {parsed.scheme}, Host: {parsed.netloc}")
                    
                    if not parsed.scheme:
                        issues.append("No URL scheme")
                    if not parsed.netloc:
                        issues.append("No hostname")
                        
                except Exception as e:
                    issues.append(f"URL parse error: {e}")
                
                if issues:
                    print(f"   ⚠️  Issues found:")
                    for issue in issues:
                        print(f"      - {issue}")
                else:
                    print(f"   ✅ URL looks valid")
                    
            except Exception as e:
                print(f"   ❌ Cannot decrypt: {e.__class__.__name__}")
            
            print("-" * 50)

if __name__ == "__main__":
    check_urls()