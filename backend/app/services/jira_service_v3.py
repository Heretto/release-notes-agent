"""
Jira Service using API v3 with direct HTTP calls.
This provides better control over API versions and requests.
"""

import httpx
import base64
import logging
from typing import List, Dict, Optional, Any
from urllib.parse import quote
import asyncio

logger = logging.getLogger(__name__)

from app.models.schemas import JiraTicket


class JiraServiceV3:
    """Service for interacting with Jira API v3."""
    
    def __init__(self, server: str, email: str, api_token: str):
        self.server = server.rstrip('/')
        self.email = email
        self.api_token = api_token
        self.base_url = f"{self.server}/rest/api/3"
        
        # Create auth header
        auth_str = f"{email}:{api_token}"
        auth_bytes = auth_str.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        self.headers = {
            "Authorization": f"Basic {auth_b64}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Jira connection and return server info."""
        try:
            async with httpx.AsyncClient() as client:
                # Test with myself endpoint (lightweight and always available)
                response = await client.get(
                    f"{self.base_url}/myself",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    return {
                        "success": True,
                        "user": {
                            "displayName": user_data.get("displayName"),
                            "emailAddress": user_data.get("emailAddress"),
                            "accountId": user_data.get("accountId")
                        },
                        "message": f"Connected as {user_data.get('displayName', 'Unknown')}"
                    }
                else:
                    logger.warning("Jira connection test failed: HTTP %s — %s", response.status_code, response.text)
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "message": f"Jira returned HTTP {response.status_code} — check your credentials and server URL"
                    }
        except Exception as e:
            logger.error("Jira connection test error: %s", e, exc_info=True)
            return {
                "success": False,
                "error": "connection_failed",
                "message": "Connection failed — check your server URL and network connectivity"
            }
    
    async def execute_query(self, jql: str, max_results: int = 100, start_at: int = 0) -> List[JiraTicket]:
        """Execute JQL query and return structured tickets."""
        try:
            async with httpx.AsyncClient() as client:
                # Use POST /rest/api/3/search/jql as per Atlassian documentation
                # https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/#api-rest-api-3-search-jql-post
                
                # Build request body matching the API specification
                request_body = {
                    "jql": jql,
                    "maxResults": max_results,
                    "fields": [
                        "summary", 
                        "description", 
                        "issuetype", 
                        "status", 
                        "priority",
                        "labels", 
                        "components", 
                        "fixVersions", 
                        "comment", 
                        "created",
                        "updated", 
                        "assignee", 
                        "reporter"
                    ],
                    "fieldsByKeys": False  # Use field names instead of keys
                }
                
                # If start_at is provided, we need to handle pagination differently
                # The new API uses startAt or nextPageToken
                if start_at > 0:
                    request_body["startAt"] = start_at
                
                # Use v3 search/jql POST endpoint
                url = f"{self.base_url}/search/jql"
                
                response = await client.post(
                    url,
                    json=request_body,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    try:
                        error_json = response.json()
                        if "errorMessages" in error_json:
                            error_text = "; ".join(error_json["errorMessages"])
                    except:
                        pass
                    raise Exception(f"Jira API error: HTTP {response.status_code} - {error_text}")
                
                data = response.json()
                issues = data.get("issues", [])
                
                # Store total count for reference (though we return List for backward compatibility)
                self.last_query_total = data.get("total", len(issues))
                
                return [self._transform_issue(issue) for issue in issues]
                
        except Exception as e:
            logger.error("Jira query error: %s", e, exc_info=True)
            raise Exception("Jira query failed — check your JQL syntax and credentials")
    
    def _transform_issue(self, issue: Dict[str, Any]) -> JiraTicket:
        """Transform Jira API v3 issue to our schema."""
        fields = issue.get("fields", {})
        
        # Extract comments
        comments = []
        comment_data = fields.get("comment", {})
        if comment_data and "comments" in comment_data:
            for comment in comment_data["comments"]:
                # In v3, comment body is in content.content array
                body = comment.get("body", "")
                if isinstance(body, dict) and "content" in body:
                    # Extract text from ADF (Atlassian Document Format)
                    text_parts = []
                    for content in body.get("content", []):
                        if content.get("type") == "paragraph":
                            for item in content.get("content", []):
                                if item.get("type") == "text":
                                    text_parts.append(item.get("text", ""))
                    comments.append(" ".join(text_parts))
                else:
                    comments.append(str(body))
        
        # Extract custom fields (any field starting with customfield_)
        custom_fields = {}
        for field_name, value in fields.items():
            if field_name.startswith('customfield_') and value is not None:
                custom_fields[field_name] = str(value)
        
        # Handle complex fields safely
        def safe_get(obj, *keys, default=None):
            """Safely navigate nested dictionaries."""
            for key in keys:
                if isinstance(obj, dict):
                    obj = obj.get(key)
                else:
                    return default
                if obj is None:
                    return default
            return obj
        
        return JiraTicket(
            key=issue.get("key"),
            summary=fields.get("summary", ""),
            description=self._extract_text_from_adf(fields.get("description")) if fields.get("description") else None,
            issue_type=safe_get(fields, "issuetype", "name", default="Unknown"),
            status=safe_get(fields, "status", "name", default="Unknown"),
            priority=safe_get(fields, "priority", "name"),
            labels=fields.get("labels", []),
            components=[comp.get("name", "") for comp in fields.get("components", [])],
            fix_versions=[ver.get("name", "") for ver in fields.get("fixVersions", [])],
            comments=comments,
            custom_fields=custom_fields
        )
    
    def _extract_text_from_adf(self, adf_content: Any) -> str:
        """Extract plain text from Atlassian Document Format."""
        if not adf_content:
            return ""
        
        if isinstance(adf_content, str):
            return adf_content
        
        if not isinstance(adf_content, dict):
            return str(adf_content)
        
        # Handle ADF format
        text_parts = []
        for content in adf_content.get("content", []):
            if content.get("type") == "paragraph":
                for item in content.get("content", []):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
            elif content.get("type") == "heading":
                for item in content.get("content", []):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
        
        return "\n".join(text_parts)
    
    async def get_projects(self) -> List[Dict[str, str]]:
        """Get list of accessible projects."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/project",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    raise Exception(f"Failed to get projects: HTTP {response.status_code}")
                
                projects = response.json()
                return [{"key": p.get("key"), "name": p.get("name")} for p in projects]
                
        except Exception as e:
            logger.error("Failed to get Jira projects: %s", e, exc_info=True)
            raise Exception("Failed to get projects — check your credentials and permissions")
    
    async def get_versions(self, project_key: str) -> List[Dict[str, str]]:
        """Get versions for a project."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/project/{project_key}/versions",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    raise Exception(f"Failed to get versions: HTTP {response.status_code}")
                
                versions = response.json()
                return [{"id": v.get("id"), "name": v.get("name")} for v in versions]
                
        except Exception as e:
            logger.error("Failed to get versions for project %s: %s", project_key, e, exc_info=True)
            raise Exception("Failed to get versions — check your credentials and project key")
    
    async def get_issue(self, issue_key: str) -> JiraTicket:
        """Get a single issue by key."""
        try:
            async with httpx.AsyncClient() as client:
                fields = [
                    "summary", "description", "issuetype", "status", "priority",
                    "labels", "components", "fixVersions", "comment", "created",
                    "updated", "assignee", "reporter"
                ]
                
                response = await client.get(
                    f"{self.base_url}/issue/{issue_key}?fields={','.join(fields)}&expand=names",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    raise Exception(f"Failed to get issue: HTTP {response.status_code}")
                
                issue_data = response.json()
                return self._transform_issue(issue_data)
                
        except Exception as e:
            logger.error("Failed to get issue %s: %s", issue_key, e, exc_info=True)
            raise Exception(f"Failed to get issue {issue_key} — check your credentials and issue key")


# Backward compatibility - use V3 by default
JiraService = JiraServiceV3