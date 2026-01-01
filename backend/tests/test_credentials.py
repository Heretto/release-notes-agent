"""Unit tests for credentials CRUD operations."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.models.database import Base, get_db
from app.config import get_settings

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

class TestCredentials:
    """Test suite for credentials endpoints."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test user and authentication."""
        # Create test user
        self.test_user = {
            "email": "test@example.com",
            "password": "testpass123"
        }
        
        # Register user
        response = client.post("/api/v1/auth/register", json=self.test_user)
        assert response.status_code in [200, 400]  # 400 if user already exists
        
        # Login to get token
        response = client.post("/api/v1/auth/login", json=self.test_user)
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        yield
        
        # Cleanup: Delete all test credentials
        response = client.get("/api/v1/credentials/jira", headers=self.headers)
        if response.status_code == 200:
            for cred in response.json():
                client.delete(f"/api/v1/credentials/jira/{cred['id']}", headers=self.headers)
    
    def test_create_jira_credential(self):
        """Test creating a new Jira credential."""
        credential_data = {
            "name": "Test Jira",
            "server_url": "https://test.atlassian.net",
            "email": "jira@example.com",
            "api_token": "test-token-123"
        }
        
        response = client.post(
            "/api/v1/credentials/jira",
            json=credential_data,
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == credential_data["name"]
        assert data["type"] == "jira"
        assert "id" in data
        
        # Store for cleanup
        self.created_id = data["id"]
    
    def test_list_jira_credentials(self):
        """Test listing Jira credentials."""
        # First create a credential
        credential_data = {
            "name": "List Test Jira",
            "server_url": "https://list-test.atlassian.net",
            "email": "list@example.com",
            "api_token": "list-token-123"
        }
        
        create_response = client.post(
            "/api/v1/credentials/jira",
            json=credential_data,
            headers=self.headers
        )
        assert create_response.status_code == 200
        created_id = create_response.json()["id"]
        
        # Now list credentials
        response = client.get("/api/v1/credentials/jira", headers=self.headers)
        assert response.status_code == 200
        
        credentials = response.json()
        assert isinstance(credentials, list)
        assert len(credentials) > 0
        
        # Check our credential is in the list
        found = any(cred["id"] == created_id for cred in credentials)
        assert found
    
    def test_update_jira_credential(self):
        """Test updating a Jira credential."""
        # First create a credential
        credential_data = {
            "name": "Update Test Jira",
            "server_url": "https://update-test.atlassian.net",
            "email": "update@example.com",
            "api_token": "update-token-123"
        }
        
        create_response = client.post(
            "/api/v1/credentials/jira",
            json=credential_data,
            headers=self.headers
        )
        assert create_response.status_code == 200
        created_id = create_response.json()["id"]
        
        # Update the credential
        update_data = {
            "name": "Updated Jira",
            "server_url": "https://updated.atlassian.net"
        }
        
        response = client.put(
            f"/api/v1/credentials/jira/{created_id}",
            json=update_data,
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
    
    def test_delete_jira_credential(self):
        """Test deleting a Jira credential."""
        # First create a credential
        credential_data = {
            "name": "Delete Test Jira",
            "server_url": "https://delete-test.atlassian.net",
            "email": "delete@example.com",
            "api_token": "delete-token-123"
        }
        
        create_response = client.post(
            "/api/v1/credentials/jira",
            json=credential_data,
            headers=self.headers
        )
        assert create_response.status_code == 200
        created_id = create_response.json()["id"]
        
        # Delete the credential
        response = client.delete(
            f"/api/v1/credentials/jira/{created_id}",
            headers=self.headers
        )
        
        assert response.status_code == 200
        
        # Verify it's deleted
        list_response = client.get("/api/v1/credentials/jira", headers=self.headers)
        credentials = list_response.json()
        found = any(cred["id"] == created_id for cred in credentials)
        assert not found
    
    def test_duplicate_name_error(self):
        """Test that creating a credential with duplicate name fails."""
        credential_data = {
            "name": "Duplicate Test",
            "server_url": "https://dup.atlassian.net",
            "email": "dup@example.com",
            "api_token": "dup-token-123"
        }
        
        # Create first credential
        response1 = client.post(
            "/api/v1/credentials/jira",
            json=credential_data,
            headers=self.headers
        )
        assert response1.status_code == 200
        
        # Try to create duplicate
        response2 = client.post(
            "/api/v1/credentials/jira",
            json=credential_data,
            headers=self.headers
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]
    
    def test_missing_fields_error(self):
        """Test that missing required fields returns an error."""
        incomplete_data = {
            "name": "Incomplete Test",
            "server_url": "https://incomplete.atlassian.net"
            # Missing email and api_token
        }
        
        response = client.post(
            "/api/v1/credentials/jira",
            json=incomplete_data,
            headers=self.headers
        )
        
        assert response.status_code == 400
        assert "Missing required" in response.json()["detail"]
    
    def test_unauthorized_access(self):
        """Test that requests without authentication are rejected."""
        response = client.get("/api/v1/credentials/jira")
        assert response.status_code == 401