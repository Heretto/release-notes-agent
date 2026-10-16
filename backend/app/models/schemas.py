from pydantic import BaseModel, EmailStr, Field, model_validator, validator
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

class OrganizationRoleEnum(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"

# User schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    organization_name: Optional[str] = None

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
class UserOrganizationInfo(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    organizations: Optional[List[UserOrganizationInfo]] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

# Instruction set schemas
CHUNKING_STRATEGIES = ("single", "by_group", "by_component")

class JqlVariableSpec(BaseModel):
    """How one {name} token in a JQL template is presented when a release is started."""
    label: str = Field("", max_length=120)
    default: str = Field("", max_length=500)
    hint: str = Field("", max_length=300)

class InstructionSetBase(BaseModel):
    name: str
    description: Optional[str] = None
    # "jql": jql_query below is the template. "releases": the query is built per Jira
    # release from jira_project and extra_jql, and jql_query is unused.
    source_mode: str = Field("jql", pattern=r'^(jql|releases)$')
    jira_project: Optional[str] = Field(None, max_length=255)
    extra_jql: Optional[str] = Field(None, max_length=2048)
    # Required in "jql" mode only — see the validator below.
    jql_query: str = Field("", max_length=4096)
    # Keyed by the {name} tokens in jql_query; normalized against them on save.
    variables: Dict[str, JqlVariableSpec] = Field(default_factory=dict)
    jira_credential_id: Optional[UUID] = None
    dita_template_id: Optional[UUID] = None
    heretto_folder_id: Optional[str] = None
    publish_to_heretto: bool = False
    is_default: bool = False
    # Agents by role: the writer writes every note's DITA and runs the workspace chat; the
    # analysis agent evaluates issues and organizes notes, falling back to the writer.
    writer_agent_id: Optional[UUID] = None
    analysis_agent_id: Optional[UUID] = None
    product_name: Optional[str] = Field(None, max_length=255)
    relevance_guidance: Optional[str] = Field(None, max_length=8000)
    organization_guidance: Optional[str] = Field(None, max_length=8000)
    chunking_strategy: str = Field("single", pattern=r'^(single|by_group|by_component)$')

    @model_validator(mode="after")
    def _require_the_fields_the_mode_uses(self):
        """Each mode needs its own field, and neither is required by the other."""
        if self.source_mode == "releases":
            if not (self.jira_project or "").strip():
                raise ValueError("A Jira project key is required when the source is Jira releases")
        elif not (self.jql_query or "").strip():
            raise ValueError("A JQL query is required")
        return self

class InstructionSetCreate(InstructionSetBase):
    pass

class InstructionSetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_mode: Optional[str] = Field(None, pattern=r'^(jql|releases)$')
    jira_project: Optional[str] = Field(None, max_length=255)
    extra_jql: Optional[str] = Field(None, max_length=2048)
    jql_query: Optional[str] = Field(None, max_length=4096)
    variables: Optional[Dict[str, JqlVariableSpec]] = None
    jira_credential_id: Optional[UUID] = None
    dita_template_id: Optional[UUID] = None
    heretto_folder_id: Optional[str] = None
    publish_to_heretto: Optional[bool] = None
    is_default: Optional[bool] = None
    writer_agent_id: Optional[UUID] = None
    analysis_agent_id: Optional[UUID] = None
    product_name: Optional[str] = Field(None, max_length=255)
    relevance_guidance: Optional[str] = Field(None, max_length=8000)
    organization_guidance: Optional[str] = Field(None, max_length=8000)
    chunking_strategy: Optional[str] = Field(None, pattern=r'^(single|by_group|by_component)$')

class InstructionSetResponse(InstructionSetBase):
    id: UUID
    user_id: UUID
    writer_agent_name: Optional[str] = None
    analysis_agent_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Job schemas
class JobCreate(BaseModel):
    # Optional: given, it overrides the instruction set's template outright (the "custom
    # query" path). Omitted, the server resolves the set's template with `variables`.
    jql_query: Optional[str] = Field(None, min_length=1, max_length=4096)
    instruction_set_id: UUID
    # {name: value} for the instruction set's JQL variables.
    variables: Dict[str, str] = Field(default_factory=dict)
    # The chosen Jira release, for an instruction set whose source is Jira releases. The
    # server builds the query from it; the browser never sends one.
    release: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    output_filename: str = Field(..., min_length=1, max_length=255)
    publish_to_heretto: bool = False
    heretto_folder_id: Optional[str] = None
    max_tickets: Optional[int] = Field(None, ge=1, le=500)  # Capped by MAX_TICKETS_PER_JOB at runtime
    chunking_strategy: Optional[str] = Field(None, pattern=r'^(single|by_group|by_component)$')

class JobUpdate(BaseModel):
    """What Edit release can change. Everything is optional; omitted means unchanged."""
    title: Optional[str] = Field(None, max_length=255)
    output_filename: Optional[str] = Field(None, min_length=1, max_length=255)
    max_tickets: Optional[int] = Field(None, ge=1, le=500)
    chunking_strategy: Optional[str] = Field(None, pattern=r'^(single|by_group|by_component)$')
    publish_to_heretto: Optional[bool] = None
    heretto_folder_id: Optional[str] = Field(None, max_length=255)
    # New values for the instruction set's JQL variables, or the chosen Jira release. Either
    # one re-resolves the query from the set's current template — the server does the
    # substituting, as everywhere else.
    variables: Optional[Dict[str, str]] = None
    release: Optional[str] = Field(None, max_length=255)

class JobProgress(BaseModel):
    stage: str
    current: int
    total: int
    message: str

class JobCounts(BaseModel):
    issues: int = 0
    relevant_issues: int = 0
    items: int = 0
    approved_items: int = 0
    attention_items: int = 0
    topics: int = 0

class JobResponse(BaseModel):
    id: UUID
    user_id: UUID
    instruction_set_id: Optional[UUID]
    # Named here so the release can say which instructions it ran on without a second
    # request, and still say so if the set is later deleted or renamed.
    instruction_set_name: Optional[str] = None
    title: Optional[str] = None
    jql_query: str
    # The variable values this run resolved its query from.
    variables: Dict[str, str] = Field(default_factory=dict)
    # False when the query was supplied by the caller rather than built from the set, which
    # is what stops a rerun rebuilding it.
    uses_instruction_query: bool = True
    # The release's own publish settings, which override the instruction set's.
    auto_publish: bool = False
    heretto_folder_id: Optional[str] = None
    status: JobStatusEnum
    triggered_by: JobTriggerEnum
    output_filename: Optional[str]
    tickets_processed: int
    max_tickets: Optional[int]
    error_message: Optional[str]
    stage: Optional[str] = None
    stage_message: Optional[str] = None
    chunking_strategy: str = "single"
    run_count: int = 0
    last_run_at: Optional[datetime] = None
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress: Optional[JobProgress] = None
    counts: Optional[JobCounts] = None

    class Config:
        from_attributes = True

# ── Workspace: issues, notes, topics, chat ──────────────────────────────────────────
class JobIssueResponse(BaseModel):
    id: UUID
    issue_key: str
    url: Optional[str] = None
    summary: str
    description: Optional[str] = None
    issue_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    fix_versions: List[str] = Field(default_factory=list)
    comments: List[str] = Field(default_factory=list)
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    jira_created: Optional[str] = None
    jira_updated: Optional[str] = None
    relevance: str
    relevance_reason: Optional[str] = None
    in_query: bool = True
    item_ids: List[UUID] = Field(default_factory=list)
    changed_at: Optional[datetime] = None

class ItemHistoryResponse(BaseModel):
    id: UUID
    event_type: str
    actor: str
    user_id: Optional[UUID] = None
    summary: str
    details: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class ReleaseNoteItemResponse(BaseModel):
    id: UUID
    job_id: UUID
    topic_id: Optional[UUID] = None
    fragment_id: str
    position: int
    group_name: Optional[str] = None
    title: str
    summary: str
    dita_content: str
    status: str
    needs_attention: bool = False
    attention_reason: Optional[str] = None
    user_edited: bool = False
    issue_keys: List[str] = Field(default_factory=list)
    has_notes: bool = False
    # Review is its own axis, separate from `status`: who was asked to read this note,
    # whether they have said they are done, and how much they said.
    reviewer_id: Optional[UUID] = None
    reviewer_email: Optional[str] = None
    reviewed: bool = False
    comment_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ItemCommentResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None
    body: str
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by_email: Optional[str] = None
    created_at: Optional[datetime] = None

class ItemCommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=8000)

class ItemCommentUpdate(BaseModel):
    resolved: bool

class ReleaseNoteItemDetailResponse(ReleaseNoteItemResponse):
    issues: List[JobIssueResponse] = Field(default_factory=list)
    notes: str = ""
    history: List[ItemHistoryResponse] = Field(default_factory=list)
    comments: List[ItemCommentResponse] = Field(default_factory=list)

class ReleaseNoteItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    summary: Optional[str] = Field(None, max_length=8000)
    dita_content: Optional[str] = Field(None, max_length=200_000)
    status: Optional[str] = Field(None, pattern=r'^(draft|review|approved|rejected)$')
    group_name: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=20_000)
    clear_attention: Optional[bool] = None
    # Sent as null to unassign, so the route tests membership in model_fields_set rather
    # than `is not None` — null here is a value, not an omission.
    reviewer_id: Optional[UUID] = None
    reviewed: Optional[bool] = None

class ReleaseNoteTopicResponse(BaseModel):
    id: UUID
    position: int
    slug: str
    title: str
    filename: str
    dita_content: str
    html: Optional[str] = None
    render_warnings: List[str] = Field(default_factory=list)
    heretto_doc_id: Optional[str] = None
    published_at: Optional[datetime] = None
    item_ids: List[UUID] = Field(default_factory=list)
    updated_at: Optional[datetime] = None

class ReassembleRequest(BaseModel):
    chunking_strategy: str = Field(..., pattern=r'^(single|by_group|by_component)$')

class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    actions: Optional[List[Dict[str, Any]]] = None
    user_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

class ChatSendRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    # The note the person is looking at, so "this one" means something.
    selected_item_id: Optional[UUID] = None

class ChatSendResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    changed_item_ids: List[UUID] = Field(default_factory=list)
    topics_changed: bool = False

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
    created_at: datetime

    class Config:
        from_attributes = True

class WebhookConfigCreateResponse(WebhookConfigResponse):
    """Returned only on creation — includes the secret token (shown once)."""
    secret_token: str

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
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    url: Optional[str] = None

class JiraPreviewRequest(BaseModel):
    jql_query: str = Field(..., min_length=1, max_length=4096)
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

# Organization schemas
class OrganizationBase(BaseModel):
    name: str
    slug: Optional[str] = None
    settings: Optional[Dict[str, Any]] = {}

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

class OrganizationResponse(OrganizationBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    member_count: Optional[int] = None
    
    class Config:
        from_attributes = True

class OrganizationMemberBase(BaseModel):
    role: OrganizationRoleEnum

class OrganizationMemberCreate(OrganizationMemberBase):
    user_email: EmailStr

class OrganizationMemberUpdate(BaseModel):
    role: OrganizationRoleEnum

class OrganizationMemberResponse(OrganizationMemberBase):
    id: UUID
    user_id: UUID
    user_email: str
    user_name: Optional[str]
    joined_at: datetime
    invited_by: Optional[UUID]
    
    class Config:
        from_attributes = True

class OrganizationInvitationCreate(BaseModel):
    email: EmailStr
    role: OrganizationRoleEnum = OrganizationRoleEnum.MEMBER

class OrganizationInvitationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    organization_name: str
    email: str
    role: OrganizationRoleEnum
    token: str
    invited_by_email: str
    expires_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True

# WebSocket events
class WebSocketEvent(BaseModel):
    event_type: str
    data: Dict[str, Any]