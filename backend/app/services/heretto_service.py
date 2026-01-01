import httpx
from typing import Optional, List

from app.models.schemas import HerettoUploadResult, HerettoFolder

class HerettoService:
    """Service for interacting with Heretto CCMS API."""
    
    def __init__(self, base_url: str, api_key: str, organization_id: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.organization_id = organization_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/xml",
            "X-Organization-Id": organization_id
        }
    
    async def upload_dita_topic(
        self, 
        content: str, 
        filename: str,
        folder_id: Optional[str] = None
    ) -> HerettoUploadResult:
        """Upload DITA topic to Heretto CCMS."""
        async with httpx.AsyncClient() as client:
            endpoint = f"{self.base_url}/api/v1/documents"
            
            payload = {
                "name": filename,
                "content": content,
                "contentType": "application/dita+xml"
            }
            if folder_id:
                payload["folderId"] = folder_id
            
            try:
                response = await client.post(
                    endpoint,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code in (200, 201):
                    data = response.json()
                    return HerettoUploadResult(
                        success=True,
                        document_id=data.get("id"),
                        message="Upload successful",
                        url=data.get("url")
                    )
                else:
                    return HerettoUploadResult(
                        success=False,
                        document_id=None,
                        message=f"Upload failed: {response.text}",
                        url=None
                    )
            except Exception as e:
                return HerettoUploadResult(
                    success=False,
                    document_id=None,
                    message=f"Upload error: {str(e)}",
                    url=None
                )
    
    async def validate_connection(self) -> bool:
        """Test Heretto API connectivity."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/health",
                    headers=self.headers,
                    timeout=10.0
                )
                return response.status_code == 200
            except:
                return False
    
    async def list_folders(self, parent_id: Optional[str] = None) -> List[HerettoFolder]:
        """List available folders in Heretto."""
        async with httpx.AsyncClient() as client:
            try:
                endpoint = f"{self.base_url}/api/v1/folders"
                params = {}
                if parent_id:
                    params["parentId"] = parent_id
                
                response = await client.get(
                    endpoint,
                    headers=self.headers,
                    params=params,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    folders = []
                    for folder in data.get("folders", []):
                        folders.append(HerettoFolder(
                            id=folder["id"],
                            name=folder["name"],
                            path=folder.get("path", "/")
                        ))
                    return folders
                else:
                    return []
            except:
                return []
    
    async def validate_dita_content(self, content: str) -> tuple[bool, Optional[str]]:
        """Validate DITA content before upload."""
        async with httpx.AsyncClient() as client:
            try:
                endpoint = f"{self.base_url}/api/v1/validate/dita"
                
                response = await client.post(
                    endpoint,
                    headers=self.headers,
                    json={"content": content},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("valid", False), data.get("message")
                else:
                    return False, "Validation failed"
            except Exception as e:
                return False, str(e)