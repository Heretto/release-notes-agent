from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

# Enums
class CredentialTypeEnum(str, Enum):
    JIRA = "jira"
    HERETTO = "heretto"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

class JobStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobTriggerEnum(str, Enum):
    MANUAL = "manual"
    WEBHOOK = "webhook"
    SCHEDULED = "scheduled"

# User schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8)

class UserResponse(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Authentication schemas
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Credential schemas
class JiraCredentials(BaseModel):
    server_url: str
    email: EmailStr
    api_token: str

class HerettoCredentials(BaseModel):
    api_key: str
    organization_id: str

class AICredentials(BaseModel):
    api_key: str
    model: Optional[str] = None

class CredentialCreate(BaseModel):
    type: CredentialTypeEnum
    name: str
    credentials: Dict[str, Any]

class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None

class CredentialResponse(BaseModel):
    id: UUID
    type: CredentialTypeEnum
    name: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class JiraCredentialResponse(BaseModel):
    id: UUID
    type: CredentialTypeEnum
    name: str
    server_url: str
    email: str
    api_token: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Instruction set schemas
class InstructionSetBase(BaseModel):
    name: str
    description: Optional[str] = None
    jql_query: str  # Jira query to execute
    system_prompt: str
    user_instructions: Optional[str] = None
    dita_template_id: Optional[UUID] = None
    is_default: bool = False

class InstructionSetCreate(InstructionSetBase):
    pass

class InstructionSetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    jql_query: Optional[str] = None
    system_prompt: Optional[str] = None
    user_instructions: Optional[str] = None
    dita_template_id: Optional[UUID] = None
    is_default: Optional[bool] = None

class InstructionSetResponse(InstructionSetBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Job schemas
class JobCreate(BaseModel):
    jql_query: str
    instruction_set_id: UUID
    ai_credential_id: Optional[UUID] = None
    additional_instructions: Optional[str] = None
    output_filename: str
    publish_to_heretto: bool = False
    heretto_folder_id: Optional[str] = None
    max_tickets: Optional[int] = None  # Maximum number of tickets to process

class JobProgress(BaseModel):
    stage: str
    current: int
    total: int
    message: str

class JobResponse(BaseModel):
    id: UUID
    user_id: UUID
    instruction_set_id: Optional[UUID]
    ai_credential_id: Optional[UUID]
    jql_query: str
    status: JobStatusEnum
    triggered_by: JobTriggerEnum
    output_filename: Optional[str]
    tickets_processed: int
    max_tickets: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress: Optional[JobProgress] = None
    
    class Config:
        from_attributes = True

# Job artifact schemas
class JobArtifactResponse(BaseModel):
    id: UUID
    artifact_type: str
    filename: str
    heretto_doc_id: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Webhook schemas
class WebhookConfigCreate(BaseModel):
    name: str
    trigger_events: List[str]
    jql_filter: Optional[str] = None
    instruction_set_id: UUID
    auto_publish: bool = False

class WebhookConfigUpdate(BaseModel):
    name: Optional[str] = None
    trigger_events: Optional[List[str]] = None
    jql_filter: Optional[str] = None
    instruction_set_id: Optional[UUID] = None
    auto_publish: Optional[bool] = None
    is_active: Optional[bool] = None

class WebhookConfigResponse(BaseModel):
    id: UUID
    name: str
    trigger_events: List[str]
    jql_filter: Optional[str]
    instruction_set_id: UUID
    auto_publish: bool
    is_active: bool
    secret_token: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# DITA template schemas
class DitaTemplateCreate(BaseModel):
    name: str
    template_type: str
    content: str

class DitaTemplateResponse(BaseModel):
    id: UUID
    name: str
    template_type: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Jira schemas
class JiraTicket(BaseModel):
    key: str
    summary: str
    description: Optional[str]
    issue_type: str
    status: str
    priority: Optional[str]
    labels: List[str]
    components: List[str]
    fix_versions: List[str]
    comments: List[str]
    custom_fields: Dict[str, str]

class JiraPreviewRequest(BaseModel):
    jql_query: str
    credential_id: UUID

class JiraPreviewResponse(BaseModel):
    count: int
    tickets: List[JiraTicket]

# Heretto schemas
class HerettoFolder(BaseModel):
    id: str
    name: str
    path: str

class HerettoUploadResult(BaseModel):
    success: bool
    document_id: Optional[str]
    message: str
    url: Optional[str]

# WebSocket events
class WebSocketEvent(BaseModel):
    event_type: str
    data: Dict[str, Any]