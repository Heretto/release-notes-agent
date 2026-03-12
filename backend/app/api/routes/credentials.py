from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.models.database import get_db, User, Credential, CredentialType
from app.models.schemas import (
    CredentialCreate,
    CredentialUpdate,
    CredentialResponse,
    JiraCredentialResponse,
    HerettoCredentialResponse,
    JiraCredentials,
    HerettoCredentials,
    AICredentials
)
from app.api.dependencies import get_current_active_user
from app.core.security import encrypt_credentials, decrypt_credentials, validate_server_url
from app.services.jira_service_v3 import JiraServiceV3
from app.services.heretto_service import HerettoService

router = APIRouter(prefix="/credentials")


def _mask_secret(value: str) -> str:
    """Mask a secret string, showing only first 4 and last 4 characters."""
    if not value or len(value) <= 8:
        return "*" * len(value) if value else ""
    return value[:4] + "*" * min(len(value) - 8, 20) + value[-4:]

# Generic credentials endpoints
@router.get("/", response_model=List[CredentialResponse])
async def list_credentials(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all credentials for current user's organization."""
    if not current_user.current_organization_id:
        return []
    credentials = db.query(Credential).filter(
        Credential.organization_id == current_user.current_organization_id
    ).all()
    return credentials

@router.post("/", response_model=CredentialResponse)
async def create_credential(
    credential_data: CredentialCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create new credential."""
    if not current_user.current_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be part of an organization to create credentials"
        )

    # Check if credential with same name exists in the organization
    existing = db.query(Credential).filter(
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == credential_data.type,
        Credential.name == credential_data.name
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credential with this name already exists"
        )

    # Encrypt and store credential
    encrypted_data = encrypt_credentials(credential_data.credentials)

    new_credential = Credential(
        user_id=current_user.id,
        organization_id=current_user.current_organization_id,
        type=credential_data.type,
        name=credential_data.name,
        encrypted_data=encrypted_data,
        created_by=current_user.email,
    )

    db.add(new_credential)
    db.commit()
    db.refresh(new_credential)

    return new_credential

# Jira-specific endpoints
@router.get("/jira", response_model=List[JiraCredentialResponse])
async def list_jira_credentials(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all Jira credentials for current user's organization."""
    # Filter by organization_id for organization-wide access
    if not current_user.current_organization_id:
        return []  # User not part of any organization
    
    credentials = db.query(Credential).filter(
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == CredentialType.JIRA
    ).all()
    
    # Decrypt and return full credential data
    result = []
    for cred in credentials:
        try:
            decrypted = decrypt_credentials(cred.encrypted_data)
            result.append(JiraCredentialResponse(
                id=cred.id,
                type=cred.type,
                name=cred.name,
                server_url=decrypted.get("server_url", ""),
                email=decrypted.get("email", ""),
                api_token=_mask_secret(decrypted.get("api_token", "")),
                created_at=cred.created_at,
                updated_at=cred.updated_at
            ))
        except Exception as e:
            print(f"[ERROR] Failed to decrypt credential {cred.id}: {e}")
            continue

    return result

@router.post("/jira", response_model=JiraCredentialResponse)
async def create_jira_credential(
    credential_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create new Jira credential for the organization."""
    # Check user has an organization
    if not current_user.current_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be part of an organization to create credentials"
        )
    
    # Check if credential with same name exists in the organization
    existing = db.query(Credential).filter(
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == CredentialType.JIRA,
        Credential.name == credential_data.get("name")
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jira credential with this name already exists"
        )
    
    # Extract and validate Jira-specific fields
    jira_creds = {
        "server_url": credential_data.get("server_url"),
        "email": credential_data.get("email"),
        "api_token": credential_data.get("api_token")
    }

    if not all(jira_creds.values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required Jira credential fields"
        )

    try:
        validate_server_url(jira_creds["server_url"])
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid server URL: {e}"
        )
    
    # Encrypt and store credential
    encrypted_data = encrypt_credentials(jira_creds)
    
    new_credential = Credential(
        user_id=current_user.id,  # Track who created it
        organization_id=current_user.current_organization_id,  # Owned by organization
        type=CredentialType.JIRA,
        name=credential_data.get("name"),
        encrypted_data=encrypted_data,
        created_by=current_user.email  # For display purposes
    )
    
    db.add(new_credential)
    db.commit()
    db.refresh(new_credential)
    
    return JiraCredentialResponse(
        id=new_credential.id,
        type=new_credential.type,
        name=new_credential.name,
        server_url=jira_creds["server_url"],
        email=jira_creds["email"],
        api_token=_mask_secret(jira_creds["api_token"]),
        created_at=new_credential.created_at,
        updated_at=new_credential.updated_at
    )

@router.put("/jira/{credential_id}", response_model=JiraCredentialResponse)
async def update_jira_credential(
    credential_id: UUID,
    credential_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update existing Jira credential."""
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == CredentialType.JIRA
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jira credential not found"
        )
    
    if credential_data.get("name"):
        credential.name = credential_data.get("name")
    
    # Get existing credentials
    existing_creds = decrypt_credentials(credential.encrypted_data)
    
    # Update encrypted data if new credentials provided
    jira_creds = {}
    if credential_data.get("server_url"):
        try:
            validate_server_url(credential_data.get("server_url"))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid server URL: {e}"
            )
        jira_creds["server_url"] = credential_data.get("server_url")
    if credential_data.get("email"):
        jira_creds["email"] = credential_data.get("email")
    api_token = credential_data.get("api_token")
    if api_token and "*" not in api_token:
        jira_creds["api_token"] = api_token

    if jira_creds:
        # Merge with existing credentials
        existing_creds.update(jira_creds)
        encrypted_data = encrypt_credentials(existing_creds)
        credential.encrypted_data = encrypted_data
    
    db.commit()
    db.refresh(credential)
    
    return JiraCredentialResponse(
        id=credential.id,
        type=credential.type,
        name=credential.name,
        server_url=existing_creds.get("server_url", ""),
        email=existing_creds.get("email", ""),
        api_token=_mask_secret(existing_creds.get("api_token", "")),
        created_at=credential.created_at,
        updated_at=credential.updated_at
    )

@router.delete("/jira/{credential_id}")
async def delete_jira_credential(
    credential_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete Jira credential."""
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == CredentialType.JIRA
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jira credential not found"
        )
    
    db.delete(credential)
    db.commit()
    
    return {"message": "Jira credential deleted successfully"}

# Heretto-specific endpoints
@router.get("/heretto", response_model=List[HerettoCredentialResponse])
async def list_heretto_credentials(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all Heretto credentials for current user's organization."""
    if not current_user.current_organization_id:
        return []

    credentials = db.query(Credential).filter(
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == CredentialType.HERETTO
    ).all()

    result = []
    for cred in credentials:
        try:
            decrypted = decrypt_credentials(cred.encrypted_data)
            result.append(HerettoCredentialResponse(
                id=cred.id,
                type=cred.type,
                name=cred.name,
                server_url=decrypted.get("server_url", ""),
                username=decrypted.get("username", ""),
                token=_mask_secret(decrypted.get("token", "")),
                created_at=cred.created_at,
                updated_at=cred.updated_at
            ))
        except Exception as e:
            print(f"[ERROR] Failed to decrypt credential {cred.id}: {e}")
            continue

    return result

@router.get("/heretto/folder-info/{folder_id}")
async def get_heretto_folder_info(
    folder_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get folder information from Heretto CCMS using the first available credential."""
    if not current_user.current_organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No organization selected")

    credential = db.query(Credential).filter(
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == CredentialType.HERETTO
    ).first()

    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Heretto credential found")

    try:
        decrypted = decrypt_credentials(credential.encrypted_data)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt Heretto credential. It may need to be re-created."
        )

    heretto_service = HerettoService(
        base_url=decrypted["server_url"],
        username=decrypted["username"],
        token=decrypted["token"]
    )

    folder = await heretto_service.get_folder_info(folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found in Heretto")

    return {
        "id": folder.id,
        "name": folder.name,
        "path": folder.path,
        "url": f"{decrypted['server_url'].rstrip('/')}/ezdnxtgen/#map-editor;folder={folder.id}"
    }

@router.post("/heretto", response_model=HerettoCredentialResponse)
async def create_heretto_credential(
    credential_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create new Heretto credential for the organization."""
    if not current_user.current_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be part of an organization to create credentials"
        )

    existing = db.query(Credential).filter(
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == CredentialType.HERETTO,
        Credential.name == credential_data.get("name")
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Heretto credential with this name already exists"
        )

    heretto_creds = {
        "server_url": credential_data.get("server_url"),
        "username": credential_data.get("username"),
        "token": credential_data.get("token")
    }

    if not all(heretto_creds.values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required Heretto credential fields"
        )

    try:
        validate_server_url(heretto_creds["server_url"])
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid server URL: {e}"
        )

    encrypted_data = encrypt_credentials(heretto_creds)

    new_credential = Credential(
        user_id=current_user.id,
        organization_id=current_user.current_organization_id,
        type=CredentialType.HERETTO,
        name=credential_data.get("name"),
        encrypted_data=encrypted_data,
        created_by=current_user.email
    )

    db.add(new_credential)
    db.commit()
    db.refresh(new_credential)

    return HerettoCredentialResponse(
        id=new_credential.id,
        type=new_credential.type,
        name=new_credential.name,
        server_url=heretto_creds["server_url"],
        username=heretto_creds["username"],
        token=_mask_secret(heretto_creds["token"]),
        created_at=new_credential.created_at,
        updated_at=new_credential.updated_at
    )

@router.put("/heretto/{credential_id}", response_model=HerettoCredentialResponse)
async def update_heretto_credential(
    credential_id: UUID,
    credential_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update existing Heretto credential."""
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == CredentialType.HERETTO
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Heretto credential not found"
        )

    if credential_data.get("name"):
        credential.name = credential_data.get("name")

    existing_creds = decrypt_credentials(credential.encrypted_data)

    heretto_creds = {}
    if credential_data.get("server_url"):
        try:
            validate_server_url(credential_data.get("server_url"))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid server URL: {e}"
            )
        heretto_creds["server_url"] = credential_data.get("server_url")
    if credential_data.get("username"):
        heretto_creds["username"] = credential_data.get("username")
    token = credential_data.get("token")
    if token and "*" not in token:
        heretto_creds["token"] = token

    if heretto_creds:
        existing_creds.update(heretto_creds)
        encrypted_data = encrypt_credentials(existing_creds)
        credential.encrypted_data = encrypted_data

    db.commit()
    db.refresh(credential)

    return HerettoCredentialResponse(
        id=credential.id,
        type=credential.type,
        name=credential.name,
        server_url=existing_creds.get("server_url", ""),
        username=existing_creds.get("username", ""),
        token=_mask_secret(existing_creds.get("token", "")),
        created_at=credential.created_at,
        updated_at=credential.updated_at
    )

@router.delete("/heretto/{credential_id}")
async def delete_heretto_credential(
    credential_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete Heretto credential."""
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == CredentialType.HERETTO
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Heretto credential not found"
        )

    db.delete(credential)
    db.commit()

    return {"message": "Heretto credential deleted successfully"}

# AI provider endpoints
@router.get("/ai")
async def list_ai_credentials(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all AI provider credentials for current user's organization."""
    if not current_user.current_organization_id:
        return []  # User not part of any organization
    
    credentials = db.query(Credential).filter(
        Credential.organization_id == current_user.current_organization_id,
        Credential.type.in_([CredentialType.GEMINI, CredentialType.OPENAI, CredentialType.ANTHROPIC])
    ).all()
    
    # Map credential type to provider name
    provider_mapping = {
        CredentialType.GEMINI: "gemini",
        CredentialType.OPENAI: "openai", 
        CredentialType.ANTHROPIC: "anthropic"
    }
    
    # Return with provider field added and model from decrypted data
    result = []
    for cred in credentials:
        # Decrypt to get model information
        try:
            decrypted_data = decrypt_credentials(cred.encrypted_data)
            model = decrypted_data.get("model", "")
        except:
            model = ""
        
        result.append({
            "id": str(cred.id),
            "type": cred.type.value,
            "provider": provider_mapping.get(cred.type, cred.type.value),
            "name": cred.name,
            "model": model if model else "Default",
            "created_at": cred.created_at.isoformat() if cred.created_at else None,
            "updated_at": cred.updated_at.isoformat() if cred.updated_at else None
        })
    
    return result

@router.post("/ai", response_model=CredentialResponse)
async def create_ai_credential(
    credential_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create new AI provider credential."""
    provider = credential_data.get("provider", "").lower()
    
    # Map provider to credential type
    type_mapping = {
        "gemini": CredentialType.GEMINI,
        "openai": CredentialType.OPENAI,
        "anthropic": CredentialType.ANTHROPIC
    }
    
    if provider not in type_mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid AI provider: {provider}"
        )
    
    credential_type = type_mapping[provider]
    
    # Check user has an organization
    if not current_user.current_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be part of an organization to create credentials"
        )
    
    # Check if credential with same name exists in the organization
    existing = db.query(Credential).filter(
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == credential_type,
        Credential.name == credential_data.get("name")
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.capitalize()} credential with this name already exists"
        )
    
    # Extract and validate AI-specific fields
    ai_creds = {
        "api_key": credential_data.get("api_key"),
        "model": credential_data.get("model", "")
    }
    
    if not ai_creds.get("api_key"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is required"
        )
    
    # Encrypt and store credential
    encrypted_data = encrypt_credentials(ai_creds)
    
    new_credential = Credential(
        user_id=current_user.id,  # Track who created it
        organization_id=current_user.current_organization_id,  # Owned by organization
        type=credential_type,
        name=credential_data.get("name"),
        encrypted_data=encrypted_data,
        created_by=current_user.email  # For display purposes
    )
    
    db.add(new_credential)
    db.commit()
    db.refresh(new_credential)
    
    return new_credential

@router.get("/ai/{credential_id}")
async def get_ai_credential(
    credential_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get single AI credential with details (API key masked)."""
    if not current_user.current_organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI credential not found")

    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.current_organization_id,
        Credential.type.in_([CredentialType.GEMINI, CredentialType.OPENAI, CredentialType.ANTHROPIC])
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI credential not found"
        )
    
    # Decrypt and return with masked API key
    decrypted = decrypt_credentials(credential.encrypted_data)
    api_key = decrypted.get("api_key", "")
    
    # Map credential type to provider name
    provider_mapping = {
        CredentialType.GEMINI: "gemini",
        CredentialType.OPENAI: "openai", 
        CredentialType.ANTHROPIC: "anthropic"
    }
    
    return {
        "id": credential.id,
        "type": credential.type,
        "name": credential.name,
        "provider": provider_mapping.get(credential.type, "unknown"),
        "api_key": _mask_secret(api_key),
        "model": decrypted.get("model", ""),
        "created_at": credential.created_at,
        "updated_at": credential.updated_at
    }

@router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: UUID,
    credential_data: CredentialUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update existing credential."""
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.current_organization_id
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    if credential_data.name:
        credential.name = credential_data.name
    
    if credential_data.credentials:
        # Get existing credentials and merge with updates
        existing_creds = decrypt_credentials(credential.encrypted_data)
        
        # Only update provided fields, keep existing values for others
        for key, value in credential_data.credentials.items():
            # Skip masked API keys (containing asterisks)
            if key == "api_key" and value and "*" in value:
                continue  # Don't update with masked keys
            existing_creds[key] = value
        
        # Re-encrypt the merged credentials
        encrypted_data = encrypt_credentials(existing_creds)
        credential.encrypted_data = encrypted_data
    
    db.commit()
    db.refresh(credential)
    
    return credential

@router.delete("/{credential_id}")
async def delete_credential(
    credential_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete credential."""
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.current_organization_id
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )
    
    db.delete(credential)
    db.commit()
    
    return {"message": "Credential deleted successfully"}

@router.post("/{credential_id}/test")
async def test_credential(
    credential_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Test credential connection with detailed response."""
    import httpx
    import base64
    from datetime import datetime
    
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.current_organization_id
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )

    # Decrypt credentials
    try:
        decrypted = decrypt_credentials(credential.encrypted_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to decrypt credential: {type(e).__name__}. The credential may need to be re-created."
        )

    try:
        if credential.type.value == "jira":
            # Make a test request to Jira API
            server_url = decrypted["server_url"].rstrip('/')
            email = decrypted["email"]
            api_token = decrypted["api_token"]
            
            # Create basic auth header
            auth_str = f"{email}:{api_token}"
            auth_bytes = auth_str.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                "Authorization": f"Basic {auth_b64}",
                "Accept": "application/json"
            }
            
            # Test with multiple endpoints to ensure connection works
            import urllib.parse
            
            # Try the simplest endpoint first - get current user
            test_url = f"{server_url}/rest/api/3/myself"
            
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # First try to get current user info (most reliable test)
                response = await client.get(test_url, headers=headers)
                
                if response.status_code == 200:
                    # Success! Now try to get some issues using POST /search/jql endpoint
                    user_data = response.json()
                    search_url = f"{server_url}/rest/api/3/search/jql"
                    search_body = {
                        "jql": "created >= -30d order by created desc",  # Search for issues created in last 30 days
                        "maxResults": 5,
                        "fields": ["summary", "status", "created", "key"]
                    }
                    search_response = await client.post(search_url, headers=headers, json=search_body, timeout=10.0)
                    
                    if search_response.status_code == 200:
                        search_data = search_response.json()
                        result = {
                            "success": True,
                            "status_code": 200,
                            "timestamp": datetime.utcnow().isoformat(),
                            "test_url": search_url,
                            "message": f"Successfully connected as {user_data.get('displayName', user_data.get('emailAddress', 'Unknown'))}. Found {search_data.get('total', 0)} accessible issues.",
                            "response_body": {
                                "user": {
                                    "displayName": user_data.get("displayName"),
                                    "emailAddress": user_data.get("emailAddress"),
                                    "accountType": user_data.get("accountType")
                                },
                                "total": search_data.get("total", 0),
                                "maxResults": search_data.get("maxResults", 0),
                                "issues": [
                                    {
                                        "key": issue.get("key"),
                                        "summary": issue.get("fields", {}).get("summary"),
                                        "status": issue.get("fields", {}).get("status", {}).get("name"),
                                        "created": issue.get("fields", {}).get("created")
                                    }
                                    for issue in search_data.get("issues", [])[:5]
                                ]
                            }
                        }
                        return result
                    else:
                        # User auth works but can't search issues
                        result = {
                            "success": True,
                            "status_code": 200,
                            "timestamp": datetime.utcnow().isoformat(),
                            "test_url": test_url,
                            "message": f"Connected as {user_data.get('displayName', 'Unknown')} but unable to search issues. Check project permissions.",
                            "response_body": {
                                "user": {
                                    "displayName": user_data.get("displayName"),
                                    "emailAddress": user_data.get("emailAddress")
                                }
                            }
                        }
                        return result
                
                # If /myself fails, continue with original response handling
                
                # Prepare detailed response
                result = {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "timestamp": datetime.utcnow().isoformat(),
                    "test_url": test_url,
                    "response_headers": dict(response.headers),
                }
                
                if response.status_code == 200:
                    response_data = response.json()
                    result["message"] = f"Successfully connected to Jira. Found {response_data.get('total', 0)} total issues."
                    result["response_body"] = {
                        "total": response_data.get("total", 0),
                        "maxResults": response_data.get("maxResults", 0),
                        "issues": [
                            {
                                "key": issue.get("key"),
                                "summary": issue.get("fields", {}).get("summary"),
                                "status": issue.get("fields", {}).get("status", {}).get("name"),
                                "created": issue.get("fields", {}).get("created")
                            }
                            for issue in response_data.get("issues", [])[:5]
                        ]
                    }
                else:
                    result["message"] = f"Connection failed: HTTP {response.status_code}"
                    try:
                        result["response_body"] = response.json()
                    except:
                        result["response_body"] = response.text
                
                return result
            
        elif credential.type.value == "heretto":
            heretto_service = HerettoService(
                base_url=decrypted["server_url"],
                username=decrypted["username"],
                token=decrypted["token"]
            )
            success = await heretto_service.validate_connection()
            return {
                "success": success,
                "status_code": 200 if success else 401,
                "message": "Heretto connection successful" if success else "Heretto connection failed",
                "timestamp": datetime.utcnow().isoformat()
            }
                
        elif credential.type.value in ["gemini", "openai", "anthropic"]:
            # Test AI provider connection with full request/response capture
            import json
            import logging
            
            try:
                api_key = decrypted.get("api_key", "")
                model = decrypted.get("model")
                provider = credential.type.value.lower()
                
                # Prepare test request details
                if provider == "anthropic":
                    api_url = "https://api.anthropic.com/v1/messages"
                    headers = {
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01",
                        "x-api-key": api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
                    }
                    request_body = {
                        "model": model or "claude-3-5-sonnet-20241022",
                        "max_tokens": 20,
                        "temperature": 0.1,
                        "system": "You are a helpful assistant.",
                        "messages": [
                            {
                                "role": "user",
                                "content": "Please respond with exactly: 'Connection successful'"
                            }
                        ]
                    }
                elif provider == "gemini":
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model or 'gemini-2.5-pro'}:generateContent"
                    headers = {
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
                    }
                    request_body = {
                        "contents": [
                            {
                                "parts": [
                                    {
                                        "text": "You are a helpful assistant. Please respond with exactly: 'Connection successful'"
                                    }
                                ]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.1,
                            "maxOutputTokens": 20
                        }
                    }
                elif provider == "openai":
                    api_url = "https://api.openai.com/v1/chat/completions"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key[:10] + '...' + api_key[-4:] if len(api_key) > 14 else '***'}"
                    }
                    # Use max_completion_tokens for newer models, with max_tokens as fallback
                    request_body = {
                        "model": model or "gpt-4-turbo-preview",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant."
                            },
                            {
                                "role": "user",
                                "content": "Please respond with exactly: 'Connection successful'"
                            }
                        ],
                        "max_completion_tokens": 20  # Changed from max_tokens for compatibility with newer models
                    }
                else:
                    api_url = "Unknown provider"
                    headers = {}
                    request_body = {}
                
                # Make the actual API call
                async with httpx.AsyncClient() as client:
                    # Build full headers for actual request (with real API key)
                    real_headers = headers.copy()
                    if provider == "anthropic":
                        real_headers["x-api-key"] = api_key
                    elif provider == "gemini":
                        real_headers["x-goog-api-key"] = api_key
                    elif provider == "openai":
                        real_headers["Authorization"] = f"Bearer {api_key}"
                    
                    # Make request
                    response = await client.post(
                        api_url if provider != "gemini" else api_url + f"?key={api_key}",
                        headers=real_headers if provider != "gemini" else {"Content-Type": "application/json"},
                        json=request_body,
                        timeout=30.0
                    )
                    
                    # Handle OpenAI parameter compatibility issue
                    if provider == "openai" and response.status_code == 400:
                        error_text = response.text
                        if "max_tokens" in error_text and "max_completion_tokens" in error_text:
                            # Retry with max_tokens instead
                            request_body["max_tokens"] = request_body.pop("max_completion_tokens")
                            response = await client.post(
                                api_url,
                                headers=real_headers,
                                json=request_body,
                                timeout=30.0
                            )
                        elif "max_completion_tokens" in error_text and "max_tokens" in error_text:
                            # This shouldn't happen since we use max_completion_tokens by default
                            pass
                    
                    # Prepare response headers (sanitize sensitive data)
                    response_headers = dict(response.headers)
                    if "x-api-key" in response_headers:
                        response_headers["x-api-key"] = "***"
                    if "authorization" in response_headers:
                        response_headers["authorization"] = "***"
                    
                    # Parse response
                    try:
                        response_data = response.json()
                    except:
                        response_data = {"text": response.text[:500] if response.text else "No response body"}
                    
                    # Special handling for Gemini 404 errors - list available models
                    if provider == "gemini" and response.status_code == 404:
                        try:
                            import google.generativeai as genai
                            genai.configure(api_key=api_key)
                            
                            # Get list of available models
                            available_models = []
                            for m in genai.list_models():
                                if 'generateContent' in m.supported_generation_methods:
                                    model_name = m.name
                                    if model_name.startswith("models/"):
                                        model_name = model_name[7:]  # Remove "models/" prefix
                                    available_models.append(model_name)
                            
                            # Create helpful error message
                            error_message = f"Model '{model or 'gemini-2.5-pro'}' not found. Available Gemini models: {', '.join(available_models)}"
                            
                            return {
                                "success": False,
                                "status_code": 404,
                                "message": error_message,
                                "timestamp": datetime.utcnow().isoformat(),
                                "request": {
                                    "url": api_url,
                                    "method": "POST",
                                    "headers": headers,  # Sanitized headers
                                    "body": request_body
                                },
                                "response": {
                                    "status_code": response.status_code,
                                    "headers": response_headers,
                                    "body": response_data,
                                    "available_models": available_models
                                }
                            }
                        except Exception as list_error:
                            # If we can't list models, return original error with suggestion
                            return {
                                "success": False,
                                "status_code": 404,
                                "message": f"Model '{model or 'gemini-2.5-pro'}' not found. Try models like: gemini-1.5-pro, gemini-1.5-flash, gemini-pro",
                                "timestamp": datetime.utcnow().isoformat(),
                                "request": {
                                    "url": api_url,
                                    "method": "POST",
                                    "headers": headers,  # Sanitized headers
                                    "body": request_body
                                },
                                "response": {
                                    "status_code": response.status_code,
                                    "headers": response_headers,
                                    "body": response_data
                                }
                            }
                    
                    return {
                        "success": response.status_code == 200,
                        "status_code": response.status_code,
                        "message": f"{provider.capitalize()} connection {'successful' if response.status_code == 200 else 'failed'}",
                        "timestamp": datetime.utcnow().isoformat(),
                        "request": {
                            "url": api_url,
                            "method": "POST",
                            "headers": headers,  # Sanitized headers
                            "body": request_body
                        },
                        "response": {
                            "status_code": response.status_code,
                            "headers": response_headers,
                            "body": response_data if isinstance(response_data, dict) else {"text": str(response_data)[:500]}
                        }
                    }
            except Exception as e:
                error_msg = str(e)
                # Extract more specific error info if available
                status_code = 500
                if "401" in error_msg or "unauthorized" in error_msg.lower():
                    status_code = 401
                elif "403" in error_msg or "forbidden" in error_msg.lower():
                    status_code = 403
                elif "404" in error_msg or "not found" in error_msg.lower():
                    status_code = 404
                elif "400" in error_msg or "invalid" in error_msg.lower():
                    status_code = 400
                    
                return {
                    "success": False,
                    "status_code": status_code,
                    "message": f"{credential.type.value.capitalize()} connection failed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "request": {
                        "provider": credential.type.value.lower(),
                        "model": decrypted.get("model", "default")
                    },
                    "error": error_msg
                }
            
        else:
            return {
                "success": False,
                "status_code": 400,
                "message": "Unknown credential type",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except httpx.ConnectError as e:
        # Connection-specific errors
        error_msg = str(e)
        if "All connection attempts failed" in error_msg:
            return {
                "success": False,
                "status_code": 503,
                "message": "Unable to connect to the server. Please check the server URL and your network connection.",
                "timestamp": datetime.utcnow().isoformat(),
                "error_details": f"Connection failed: {error_msg}",
                "troubleshooting": [
                    "Verify the server URL is correct",
                    "Check if the server is accessible from your network",
                    "Ensure there are no firewall or proxy issues",
                    "Try accessing the URL directly in a browser"
                ]
            }
        return {
            "success": False,
            "status_code": 503,
            "message": f"Connection error: {error_msg}",
            "timestamp": datetime.utcnow().isoformat(),
            "error_details": str(e)
        }
    except httpx.TimeoutException as e:
        return {
            "success": False,
            "status_code": 504,
            "message": "Connection timed out. The server took too long to respond.",
            "timestamp": datetime.utcnow().isoformat(),
            "error_details": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 500,
            "message": f"Test failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
            "error_details": str(e)
        }

@router.post("/{credential_id}/test-upload")
async def test_heretto_upload(
    credential_id: UUID,
    body: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Test creating a file in Heretto CCMS using a credential."""
    from datetime import datetime

    folder_id = body.get("folder_id")
    if not folder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="folder_id is required"
        )

    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.organization_id == current_user.current_organization_id,
        Credential.type == CredentialType.HERETTO
    ).first()

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Heretto credential not found"
        )

    try:
        decrypted = decrypt_credentials(credential.encrypted_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to decrypt credential: {type(e).__name__}. The credential may need to be re-created."
        )

    heretto_service = HerettoService(
        base_url=decrypted["server_url"],
        username=decrypted["username"],
        token=decrypted["token"]
    )

    # Create a small test DITA topic
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    test_filename = f"connection-test-{timestamp}.dita"
    test_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="connection-test-{timestamp}">
  <title>Connection Test — {timestamp}</title>
  <body>
    <p>This file was created by the Release Notes Agent to verify the Heretto CCMS connection.</p>
    <p>Created at: {datetime.utcnow().isoformat()}Z</p>
  </body>
</topic>"""

    result = await heretto_service.upload_dita_topic(
        content=test_content,
        filename=test_filename,
        folder_id=folder_id
    )

    return {
        "success": result.success,
        "status_code": 201 if result.success else 400,
        "message": result.message,
        "timestamp": datetime.utcnow().isoformat(),
        "document_id": result.document_id,
        "url": result.url,
        "test_filename": test_filename
    }