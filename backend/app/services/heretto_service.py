import httpx
import base64
import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional, List

from app.models.schemas import HerettoUploadResult, HerettoFolder

logger = logging.getLogger(__name__)

_HERETTO_ID_RE = re.compile(r'^[a-zA-Z0-9_\-]+$')


def _validate_heretto_id(value: str, label: str = "ID") -> str:
    """Validate a Heretto resource ID to prevent path traversal."""
    if not value or len(value) > 256 or not _HERETTO_ID_RE.match(value):
        raise ValueError(f"Invalid Heretto {label}: must be alphanumeric, hyphens, or underscores")
    return value


class HerettoService:
    """Service for interacting with Heretto CCMS REST API.

    Authentication uses HTTP Basic Auth (username:token).
    API reference: Heretto CCMS API Reference Guide.
    """

    def __init__(self, base_url: str, username: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.token = token
        auth_str = f"{username}:{token}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        self.auth_header = f"Basic {auth_b64}"

    def _headers(self, content_type: str = "application/xml") -> dict:
        return {
            "Authorization": self.auth_header,
            "Content-Type": content_type,
        }

    async def upload_dita_topic(
        self,
        content: str,
        filename: str,
        folder_id: Optional[str] = None
    ) -> HerettoUploadResult:
        """Upload a DITA topic to Heretto CCMS.

        Two-step process per the Heretto REST API:
        1. POST to /rest/all-files/{folder-id} to create the document placeholder.
        2. PUT  to /rest/all-files/{document-id}/content to upload the content.
        """
        if not folder_id:
            return HerettoUploadResult(
                success=False,
                document_id=None,
                message="No folder ID provided — cannot upload to Heretto",
                url=None
            )

        try:
            _validate_heretto_id(folder_id, "folder ID")
        except ValueError as e:
            return HerettoUploadResult(
                success=False,
                document_id=None,
                message=str(e),
                url=None
            )

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Step 1: Create the document placeholder
                create_url = f"{self.base_url}/rest/all-files/{folder_id}"
                resource_xml = (
                    f"<resource>"
                    f"<name>{_escape_xml(filename)}</name>"
                    f"<mime-type>application/xml</mime-type>"
                    f"</resource>"
                )

                logger.info(f"Creating document placeholder in folder {folder_id}: {filename}")
                create_resp = await client.post(
                    create_url,
                    headers=self._headers(),
                    content=resource_xml,
                )

                if create_resp.status_code not in (200, 201):
                    logger.error("Heretto create placeholder failed: HTTP %s — %s", create_resp.status_code, create_resp.text)
                    return HerettoUploadResult(
                        success=False,
                        document_id=None,
                        message=f"Failed to create document placeholder: HTTP {create_resp.status_code}",
                        url=None
                    )

                # Parse the document UUID from the response XML
                doc_id = _parse_resource_id(create_resp.text)
                if not doc_id:
                    logger.error("Could not parse resource ID from Heretto response: %s", create_resp.text[:500])
                    return HerettoUploadResult(
                        success=False,
                        document_id=None,
                        message="Created document but could not parse resource ID from response",
                        url=None
                    )

                logger.info(f"Document placeholder created with ID: {doc_id}")

                # Step 2: Upload the actual DITA content
                content_url = f"{self.base_url}/rest/all-files/{doc_id}/content"

                logger.info(f"Uploading DITA content to document {doc_id}")
                put_resp = await client.put(
                    content_url,
                    headers=self._headers(),
                    content=content.encode("utf-8"),
                )

                if put_resp.status_code not in (200, 201):
                    logger.error("Heretto content upload failed: HTTP %s — %s", put_resp.status_code, put_resp.text)
                    return HerettoUploadResult(
                        success=False,
                        document_id=doc_id,
                        message=f"Document created but content upload failed: HTTP {put_resp.status_code}",
                        url=None
                    )

                logger.info(f"DITA content uploaded successfully to document {doc_id}")
                doc_url = f"{self.base_url}/rest/all-files/{doc_id}"
                return HerettoUploadResult(
                    success=True,
                    document_id=doc_id,
                    message="Upload successful",
                    url=doc_url
                )

            except httpx.TimeoutException:
                return HerettoUploadResult(
                    success=False,
                    document_id=None,
                    message="Upload timed out — the Heretto server took too long to respond",
                    url=None
                )
            except Exception as e:
                logger.error("Heretto upload error: %s", e, exc_info=True)
                return HerettoUploadResult(
                    success=False,
                    document_id=None,
                    message="Upload failed — check your Heretto credentials and folder configuration",
                    url=None
                )

    async def validate_connection(self) -> bool:
        """Test Heretto API connectivity by listing branches."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # GET /rest/branches/ is a lightweight call that requires auth
                response = await client.get(
                    f"{self.base_url}/rest/branches/",
                    headers=self._headers("application/xml"),
                )
                return response.status_code == 200
            except Exception:
                return False

    async def get_folder_info(self, folder_id: str) -> Optional[HerettoFolder]:
        """Get information about a specific folder by its ID."""
        try:
            _validate_heretto_id(folder_id, "folder ID")
        except ValueError:
            return None

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                endpoint = f"{self.base_url}/rest/all-files/{folder_id}"
                response = await client.get(
                    endpoint,
                    headers=self._headers("application/xml"),
                )

                if response.status_code != 200:
                    return None

                root = ET.fromstring(response.text)
                if root.tag != "folder":
                    return None

                name_el = root.find("name")
                uri_el = root.find("xmldb-uri")
                return HerettoFolder(
                    id=root.get("id", folder_id),
                    name=name_el.text if name_el is not None and name_el.text else "",
                    path=uri_el.text if uri_el is not None and uri_el.text else "/"
                )
            except Exception:
                return None

    async def list_folders(self, parent_id: Optional[str] = None) -> List[HerettoFolder]:
        """List child folders inside a parent folder."""
        if not parent_id:
            return []

        try:
            _validate_heretto_id(parent_id, "parent folder ID")
        except ValueError:
            return []

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                endpoint = f"{self.base_url}/rest/all-files/{parent_id}"
                response = await client.get(
                    endpoint,
                    headers=self._headers("application/xml"),
                )

                if response.status_code != 200:
                    return []

                root = ET.fromstring(response.text)
                folders = []
                children = root.find("children")
                if children is not None:
                    for folder_el in children.findall("folder"):
                        folders.append(HerettoFolder(
                            id=folder_el.get("id", ""),
                            name=folder_el.get("name", ""),
                            path=folder_el.get("xmldb-uri", "/")
                        ))
                return folders
            except Exception:
                return []


def _escape_xml(text: str) -> str:
    """Escape special characters for XML text content."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _parse_resource_id(xml_text: str) -> Optional[str]:
    """Extract the resource id attribute from a Heretto response XML."""
    try:
        root = ET.fromstring(xml_text)
        return root.get("id")
    except ET.ParseError:
        return None
