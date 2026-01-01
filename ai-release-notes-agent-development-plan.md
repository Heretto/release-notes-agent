# AI Release Notes Agent Development Plan

## Executive Summary

This document outlines the development plan for an AI-powered agent that automates the creation of release notes in DITA format. The agent integrates with Jira for ticket extraction, uses Google Gemini for content generation, and publishes to Heretto CCMS. The system features an Angular frontend for configuration and monitoring, with a Python backend handling AI orchestration and API integrations.

---

## 1. Project Overview

### 1.1 Objectives

- Automate extraction of Jira tickets based on configurable queries
- Generate professionally-written release notes in valid DITA topic format
- Support customizable instructions for content generation style and structure
- Provide secure credential management for Jira and Heretto integrations
- Enable both manual triggering and automated webhook-based workflows
- Design for model flexibility with Google Gemini as the primary AI provider

### 1.2 Key Stakeholders

| Role | Responsibility |
|------|----------------|
| Technical Writers | Define release note templates, review generated content |
| Product Managers | Configure Jira queries, approve release notes |
| DevOps/IT | Deploy and maintain infrastructure, manage credentials |
| Developers | Integrate webhook triggers into CI/CD pipelines |

### 1.3 Success Criteria

- Reduction in manual release note drafting time by 70%+
- Generated DITA topics pass validation against DITA 1.3 schema
- Successful integration with existing Heretto CCMS workflows
- System uptime of 99.5% for webhook processing

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ANGULAR FRONTEND                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Dashboard   │  │  Credentials │  │  Instructions│  │   Job Queue  │    │
│  │              │  │  Management  │  │   Editor     │  │   Monitor    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ REST API / WebSocket
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PYTHON BACKEND                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                           FastAPI Application                         │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │  │
│  │  │  REST API  │  │  Webhook   │  │    Auth    │  │  WebSocket │     │  │
│  │  │  Endpoints │  │  Handler   │  │  Middleware│  │  Server    │     │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          Core Services Layer                          │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │  │
│  │  │  Jira Service  │  │   AI Service   │  │ Heretto Service│         │  │
│  │  │                │  │  (Model Agnostic│  │                │         │  │
│  │  │  - Query       │  │   Interface)   │  │  - Upload      │         │  │
│  │  │  - Extract     │  │                │  │  - Validate    │         │  │
│  │  │  - Transform   │  │  ┌──────────┐  │  │  - Publish     │         │  │
│  │  └────────────────┘  │  │  Gemini  │  │  └────────────────┘         │  │
│  │                      │  │  Adapter │  │                              │  │
│  │  ┌────────────────┐  │  └──────────┘  │  ┌────────────────┐         │  │
│  │  │ DITA Generator │  │  ┌──────────┐  │  │ Job Queue      │         │  │
│  │  │                │  │  │  OpenAI  │  │  │ (Celery/Redis) │         │  │
│  │  │  - Templates   │  │  │  Adapter │  │  │                │         │  │
│  │  │  - Validation  │  │  └──────────┘  │  │  - Async Tasks │         │  │
│  │  │  - Formatting  │  │  ┌──────────┐  │  │  - Retries     │         │  │
│  │  └────────────────┘  │  │  Claude  │  │  │  - Scheduling  │         │  │
│  │                      │  │  Adapter │  │  └────────────────┘         │  │
│  │                      │  └──────────┘  │                              │  │
│  │                      └────────────────┘                              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          Data Layer                                   │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │  │
│  │  │   PostgreSQL   │  │     Redis      │  │  File Storage  │         │  │
│  │  │                │  │                │  │                │         │  │
│  │  │  - Credentials │  │  - Job Queue   │  │  - DITA Drafts │         │  │
│  │  │  - Instructions│  │  - Cache       │  │  - Templates   │         │  │
│  │  │  - Job History │  │  - Sessions    │  │  - Logs        │         │  │
│  │  └────────────────┘  └────────────────┘  └────────────────┘         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                                       │
                    ▼                                       ▼
        ┌───────────────────┐                   ┌───────────────────┐
        │       JIRA        │                   │   HERETTO CCMS    │
        │                   │                   │                   │
        │  - REST API       │                   │  - REST API       │
        │  - Webhooks       │                   │  - Content Upload │
        │  - JQL Queries    │                   │  - DITA Validation│
        └───────────────────┘                   └───────────────────┘
```

### 2.2 Technology Stack

| Layer | Technology | Justification |
|-------|------------|---------------|
| Frontend | Angular 17+ | Required per specification; strong typing, enterprise-ready |
| UI Components | Angular Material | Consistent design system, accessibility support |
| State Management | NgRx | Predictable state for complex async operations |
| Backend Framework | FastAPI | Async support, automatic OpenAPI docs, Python native |
| AI Library | google-generativeai | Official Google library for Gemini access |
| Task Queue | Celery + Redis | Reliable async job processing with retries |
| Database | PostgreSQL | Robust relational storage for credentials and config |
| Cache | Redis | Fast caching and session management |
| Authentication | JWT + OAuth2 | Industry-standard secure authentication |
| DITA Validation | lxml + DITA-OT | Schema validation and transformation |

### 2.3 Data Flow

```
1. TRIGGER (Manual or Webhook)
        │
        ▼
2. JIRA EXTRACTION
   - Execute JQL query
   - Retrieve ticket details (summary, description, comments, linked issues)
   - Transform to structured format
        │
        ▼
3. CONTEXT ASSEMBLY
   - Load user-defined instructions
   - Load DITA templates
   - Combine with extracted ticket data
        │
        ▼
4. AI GENERATION
   - Send context to Gemini API
   - Stream or batch response
   - Parse generated DITA content
        │
        ▼
5. VALIDATION & REVIEW
   - Validate against DITA 1.3 schema
   - Store draft for human review (optional)
   - Apply any post-processing rules
        │
        ▼
6. HERETTO PUBLISHING
   - Authenticate with Heretto API
   - Upload DITA topic(s)
   - Confirm successful storage
        │
        ▼
7. NOTIFICATION
   - Update job status
   - Notify via WebSocket/email
   - Log completion metrics
```

---

## 3. Component Specifications

### 3.1 Backend Components (Python)

#### 3.1.1 Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry
│   ├── config.py                  # Configuration management
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── auth.py            # Authentication endpoints
│   │   │   ├── credentials.py     # Credential management
│   │   │   ├── instructions.py    # Custom instruction CRUD
│   │   │   ├── jobs.py            # Job triggering and status
│   │   │   ├── webhooks.py        # Jira webhook handler
│   │   │   └── health.py          # Health check endpoints
│   │   └── dependencies.py        # Shared dependencies
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py            # JWT, encryption utilities
│   │   ├── exceptions.py          # Custom exception classes
│   │   └── logging.py             # Structured logging setup
│   ├── services/
│   │   ├── __init__.py
│   │   ├── jira_service.py        # Jira API integration
│   │   ├── ai_service.py          # Model-agnostic AI interface
│   │   ├── gemini_adapter.py      # Google Gemini implementation
│   │   ├── dita_generator.py      # DITA topic generation
│   │   ├── dita_validator.py      # DITA schema validation
│   │   ├── heretto_service.py     # Heretto CCMS integration
│   │   └── job_orchestrator.py    # Workflow coordination
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLAlchemy models
│   │   ├── schemas.py             # Pydantic schemas
│   │   └── enums.py               # Enumeration types
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py          # Celery configuration
│   │   └── release_notes.py       # Async release note tasks
│   └── templates/
│       ├── dita/
│       │   ├── topic.xml          # Base topic template
│       │   ├── release_note.xml   # Release note template
│       │   └── concept.xml        # Concept topic template
│       └── prompts/
│           ├── system_prompt.txt  # Base system instructions
│           └── release_note.txt   # Release note generation prompt
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── alembic/                       # Database migrations
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
└── docker-compose.yml
```

#### 3.1.2 Core Service Interfaces

**AI Service Interface (Model-Agnostic)**

```python
# app/services/ai_service.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from pydantic import BaseModel

class GenerationRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    max_tokens: Optional[int] = 4096
    temperature: Optional[float] = 0.7
    
class GenerationResponse(BaseModel):
    content: str
    model: str
    usage: dict
    finish_reason: str

class AIServiceInterface(ABC):
    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate content synchronously"""
        pass
    
    @abstractmethod
    async def generate_stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Generate content with streaming"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier"""
        pass
```

**Gemini Adapter Implementation**

```python
# app/services/gemini_adapter.py
import google.generativeai as genai
from typing import AsyncIterator
from .ai_service import AIServiceInterface, GenerationRequest, GenerationResponse

class GeminiAdapter(AIServiceInterface):
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self._model_name = model_name
    
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        response = await self.model.generate_content_async(
            contents=[
                {"role": "user", "parts": [request.system_prompt + "\n\n" + request.user_prompt]}
            ],
            generation_config=genai.GenerationConfig(
                max_output_tokens=request.max_tokens,
                temperature=request.temperature
            )
        )
        return GenerationResponse(
            content=response.text,
            model=self._model_name,
            usage={"prompt_tokens": 0, "completion_tokens": 0},  # Gemini usage tracking
            finish_reason=response.candidates[0].finish_reason.name
        )
    
    async def generate_stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        response = await self.model.generate_content_async(
            contents=[
                {"role": "user", "parts": [request.system_prompt + "\n\n" + request.user_prompt]}
            ],
            generation_config=genai.GenerationConfig(
                max_output_tokens=request.max_tokens,
                temperature=request.temperature
            ),
            stream=True
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text
    
    def get_model_name(self) -> str:
        return self._model_name
```

**Jira Service**

```python
# app/services/jira_service.py
from jira import JIRA
from typing import List, Optional
from pydantic import BaseModel

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
    custom_fields: dict

class JiraService:
    def __init__(self, server: str, email: str, api_token: str):
        self.client = JIRA(server=server, basic_auth=(email, api_token))
    
    async def execute_query(self, jql: str, max_results: int = 100) -> List[JiraTicket]:
        """Execute JQL query and return structured tickets"""
        issues = self.client.search_issues(jql, maxResults=max_results, expand="comments")
        return [self._transform_issue(issue) for issue in issues]
    
    def _transform_issue(self, issue) -> JiraTicket:
        return JiraTicket(
            key=issue.key,
            summary=issue.fields.summary,
            description=issue.fields.description,
            issue_type=issue.fields.issuetype.name,
            status=issue.fields.status.name,
            priority=issue.fields.priority.name if issue.fields.priority else None,
            labels=issue.fields.labels,
            components=[c.name for c in issue.fields.components],
            fix_versions=[v.name for v in issue.fields.fixVersions],
            comments=[c.body for c in issue.fields.comment.comments],
            custom_fields=self._extract_custom_fields(issue)
        )
    
    def _extract_custom_fields(self, issue) -> dict:
        """Extract relevant custom fields"""
        custom = {}
        for field_name, field_value in issue.fields.__dict__.items():
            if field_name.startswith('customfield_') and field_value:
                custom[field_name] = str(field_value)
        return custom
```

**Heretto Service**

```python
# app/services/heretto_service.py
import httpx
from typing import Optional
from pydantic import BaseModel

class HerettoUploadResult(BaseModel):
    success: bool
    document_id: Optional[str]
    message: str
    url: Optional[str]

class HerettoService:
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
        """Upload DITA topic to Heretto CCMS"""
        async with httpx.AsyncClient() as client:
            endpoint = f"{self.base_url}/api/v1/documents"
            
            payload = {
                "name": filename,
                "content": content,
                "contentType": "application/dita+xml"
            }
            if folder_id:
                payload["folderId"] = folder_id
            
            response = await client.post(
                endpoint,
                headers=self.headers,
                json=payload
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
    
    async def validate_connection(self) -> bool:
        """Test Heretto API connectivity"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/health",
                headers=self.headers
            )
            return response.status_code == 200
```

#### 3.1.3 Webhook Handler

```python
# app/api/routes/webhooks.py
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from app.services.job_orchestrator import JobOrchestrator
from app.core.security import verify_jira_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/jira")
async def handle_jira_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    orchestrator: JobOrchestrator = Depends(get_orchestrator)
):
    """Handle incoming Jira webhooks"""
    # Verify webhook signature
    signature = request.headers.get("X-Hub-Signature")
    body = await request.body()
    
    if not verify_jira_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    payload = await request.json()
    
    # Extract relevant event data
    event_type = payload.get("webhookEvent")
    issue_key = payload.get("issue", {}).get("key")
    
    # Determine if this event should trigger release note generation
    if event_type in ("jira:issue_updated", "jira:version_released"):
        # Queue the job for async processing
        background_tasks.add_task(
            orchestrator.process_webhook_event,
            event_type=event_type,
            issue_key=issue_key,
            payload=payload
        )
    
    return {"status": "accepted", "event": event_type}
```

### 3.2 Frontend Components (Angular)

#### 3.2.1 Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── core/
│   │   │   ├── auth/
│   │   │   │   ├── auth.guard.ts
│   │   │   │   ├── auth.interceptor.ts
│   │   │   │   └── auth.service.ts
│   │   │   ├── services/
│   │   │   │   ├── api.service.ts
│   │   │   │   ├── credentials.service.ts
│   │   │   │   ├── jobs.service.ts
│   │   │   │   └── websocket.service.ts
│   │   │   └── models/
│   │   │       ├── credential.model.ts
│   │   │       ├── job.model.ts
│   │   │       └── instruction.model.ts
│   │   ├── features/
│   │   │   ├── dashboard/
│   │   │   │   ├── dashboard.component.ts
│   │   │   │   ├── dashboard.component.html
│   │   │   │   ├── job-status-card/
│   │   │   │   └── recent-jobs-table/
│   │   │   ├── credentials/
│   │   │   │   ├── credentials.component.ts
│   │   │   │   ├── jira-credentials-form/
│   │   │   │   ├── heretto-credentials-form/
│   │   │   │   └── ai-credentials-form/
│   │   │   ├── instructions/
│   │   │   │   ├── instructions.component.ts
│   │   │   │   ├── instruction-editor/
│   │   │   │   └── instruction-templates/
│   │   │   ├── jobs/
│   │   │   │   ├── jobs.component.ts
│   │   │   │   ├── job-creator/
│   │   │   │   ├── job-detail/
│   │   │   │   └── job-queue/
│   │   │   └── settings/
│   │   │       ├── settings.component.ts
│   │   │       ├── model-selector/
│   │   │       └── webhook-config/
│   │   ├── shared/
│   │   │   ├── components/
│   │   │   │   ├── loading-spinner/
│   │   │   │   ├── confirmation-dialog/
│   │   │   │   └── toast-notification/
│   │   │   └── pipes/
│   │   ├── store/                  # NgRx state management
│   │   │   ├── credentials/
│   │   │   ├── jobs/
│   │   │   └── app.state.ts
│   │   ├── app.component.ts
│   │   ├── app.config.ts
│   │   └── app.routes.ts
│   ├── assets/
│   ├── environments/
│   └── styles/
├── angular.json
├── package.json
└── tsconfig.json
```

#### 3.2.2 Key Component Specifications

**Credentials Management Component**

```typescript
// src/app/features/credentials/jira-credentials-form/jira-credentials-form.component.ts
import { Component, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { CredentialsService } from '../../../core/services/credentials.service';

@Component({
  selector: 'app-jira-credentials-form',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <form [formGroup]="credentialsForm" (ngSubmit)="onSubmit()">
      <h3>Jira Credentials</h3>
      
      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Jira Server URL</mat-label>
        <input matInput formControlName="serverUrl" placeholder="https://your-domain.atlassian.net">
        <mat-error *ngIf="credentialsForm.get('serverUrl')?.hasError('required')">
          Server URL is required
        </mat-error>
        <mat-error *ngIf="credentialsForm.get('serverUrl')?.hasError('pattern')">
          Please enter a valid URL
        </mat-error>
      </mat-form-field>

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>Email</mat-label>
        <input matInput formControlName="email" type="email">
      </mat-form-field>

      <mat-form-field appearance="outline" class="full-width">
        <mat-label>API Token</mat-label>
        <input matInput formControlName="apiToken" [type]="hideToken ? 'password' : 'text'">
        <button mat-icon-button matSuffix (click)="hideToken = !hideToken" type="button">
          <mat-icon>{{hideToken ? 'visibility_off' : 'visibility'}}</mat-icon>
        </button>
      </mat-form-field>

      <div class="button-row">
        <button mat-button type="button" (click)="testConnection()" [disabled]="testing">
          {{ testing ? 'Testing...' : 'Test Connection' }}
        </button>
        <button mat-raised-button color="primary" type="submit" [disabled]="!credentialsForm.valid || saving">
          {{ saving ? 'Saving...' : 'Save Credentials' }}
        </button>
      </div>

      <div *ngIf="connectionStatus" class="status-message" [class.success]="connectionStatus.success">
        {{ connectionStatus.message }}
      </div>
    </form>
  `
})
export class JiraCredentialsFormComponent {
  private fb = inject(FormBuilder);
  private credentialsService = inject(CredentialsService);

  hideToken = true;
  testing = false;
  saving = false;
  connectionStatus: { success: boolean; message: string } | null = null;

  credentialsForm: FormGroup = this.fb.group({
    serverUrl: ['', [Validators.required, Validators.pattern(/^https?:\/\/.+/)]],
    email: ['', [Validators.required, Validators.email]],
    apiToken: ['', Validators.required]
  });

  async testConnection() {
    this.testing = true;
    this.connectionStatus = null;
    
    try {
      const result = await this.credentialsService.testJiraConnection(
        this.credentialsForm.value
      );
      this.connectionStatus = result;
    } finally {
      this.testing = false;
    }
  }

  async onSubmit() {
    if (this.credentialsForm.valid) {
      this.saving = true;
      try {
        await this.credentialsService.saveJiraCredentials(this.credentialsForm.value);
      } finally {
        this.saving = false;
      }
    }
  }
}
```

**Job Creator Component with JQL Builder**

```typescript
// src/app/features/jobs/job-creator/job-creator.component.ts
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { JobsService } from '../../../core/services/jobs.service';
import { InstructionSet } from '../../../core/models/instruction.model';

@Component({
  selector: 'app-job-creator',
  standalone: true,
  template: `
    <mat-card>
      <mat-card-header>
        <mat-card-title>Create Release Notes Job</mat-card-title>
      </mat-card-header>
      
      <mat-card-content>
        <form [formGroup]="jobForm" (ngSubmit)="createJob()">
          
          <!-- JQL Query Section -->
          <section class="form-section">
            <h4>Jira Query</h4>
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>JQL Query</mat-label>
              <textarea matInput formControlName="jqlQuery" rows="3"
                placeholder="project = MYPROJ AND fixVersion = '2.0.0' AND status = Done">
              </textarea>
              <mat-hint>Enter JQL to select tickets for release notes</mat-hint>
            </mat-form-field>
            
            <button mat-stroked-button type="button" (click)="previewQuery()">
              Preview Results ({{ previewCount() }} tickets)
            </button>
          </section>

          <!-- Instructions Section -->
          <section class="form-section">
            <h4>Generation Instructions</h4>
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Instruction Set</mat-label>
              <mat-select formControlName="instructionSetId">
                @for (instruction of instructionSets(); track instruction.id) {
                  <mat-option [value]="instruction.id">{{ instruction.name }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Additional Instructions (Optional)</mat-label>
              <textarea matInput formControlName="additionalInstructions" rows="4"
                placeholder="Any specific instructions for this job...">
              </textarea>
            </mat-form-field>
          </section>

          <!-- Output Configuration -->
          <section class="form-section">
            <h4>Output Settings</h4>
            <mat-form-field appearance="outline">
              <mat-label>Output Filename</mat-label>
              <input matInput formControlName="outputFilename" placeholder="release-notes-v2.0.0.dita">
            </mat-form-field>
            
            <mat-checkbox formControlName="publishToHeretto">
              Automatically publish to Heretto CCMS
            </mat-checkbox>
            
            <mat-form-field appearance="outline" *ngIf="jobForm.get('publishToHeretto')?.value">
              <mat-label>Heretto Folder</mat-label>
              <mat-select formControlName="herettoFolderId">
                <!-- Folder options populated from Heretto -->
              </mat-select>
            </mat-form-field>
          </section>

          <div class="form-actions">
            <button mat-raised-button color="primary" type="submit" 
                    [disabled]="!jobForm.valid || creating()">
              {{ creating() ? 'Creating...' : 'Create Job' }}
            </button>
          </div>
        </form>
      </mat-card-content>
    </mat-card>
  `
})
export class JobCreatorComponent {
  private fb = inject(FormBuilder);
  private jobsService = inject(JobsService);

  instructionSets = signal<InstructionSet[]>([]);
  previewCount = signal<number>(0);
  creating = signal<boolean>(false);

  jobForm: FormGroup = this.fb.group({
    jqlQuery: ['', Validators.required],
    instructionSetId: ['', Validators.required],
    additionalInstructions: [''],
    outputFilename: ['', Validators.required],
    publishToHeretto: [true],
    herettoFolderId: ['']
  });

  async previewQuery() {
    const jql = this.jobForm.get('jqlQuery')?.value;
    if (jql) {
      const count = await this.jobsService.previewJqlQuery(jql);
      this.previewCount.set(count);
    }
  }

  async createJob() {
    if (this.jobForm.valid) {
      this.creating.set(true);
      try {
        await this.jobsService.createJob(this.jobForm.value);
      } finally {
        this.creating.set(false);
      }
    }
  }
}
```

---

## 4. Database Schema

### 4.1 Entity Relationship Diagram

```
┌─────────────────────┐       ┌─────────────────────┐
│      users          │       │    credentials      │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │───┐   │ id (PK)             │
│ email               │   │   │ user_id (FK)        │
│ password_hash       │   └──►│ type (enum)         │
│ created_at          │       │ name                │
│ updated_at          │       │ encrypted_data      │
└─────────────────────┘       │ created_at          │
                              │ updated_at          │
                              └─────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────┐       ┌─────────────────────┐
│  instruction_sets   │       │       jobs          │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │   ┌───│ id (PK)             │
│ user_id (FK)        │   │   │ user_id (FK)        │
│ name                │◄──┼───│ instruction_set_id  │
│ description         │   │   │ jql_query           │
│ system_prompt       │   │   │ status (enum)       │
│ user_instructions   │   │   │ triggered_by        │
│ dita_template_id    │   │   │ output_filename     │
│ is_default          │   │   │ error_message       │
│ created_at          │   │   │ created_at          │
│ updated_at          │   │   │ started_at          │
└─────────────────────┘   │   │ completed_at        │
                          │   └─────────────────────┘
                          │              │
                          │              │ 1:N
                          │              ▼
┌─────────────────────┐   │   ┌─────────────────────┐
│   dita_templates    │   │   │   job_artifacts     │
├─────────────────────┤   │   ├─────────────────────┤
│ id (PK)             │   │   │ id (PK)             │
│ user_id (FK)        │   │   │ job_id (FK)         │
│ name                │   │   │ artifact_type       │
│ template_type       │   │   │ filename            │
│ content             │   │   │ content             │
│ created_at          │   │   │ heretto_doc_id      │
│ updated_at          │   │   │ created_at          │
└─────────────────────┘   │   └─────────────────────┘
                          │
                          │
┌─────────────────────┐   │
│  webhook_configs    │   │
├─────────────────────┤   │
│ id (PK)             │   │
│ user_id (FK)        │───┘
│ name                │
│ trigger_events      │
│ jql_filter          │
│ instruction_set_id  │
│ auto_publish        │
│ is_active           │
│ secret_token        │
│ created_at          │
└─────────────────────┘
```

### 4.2 Key Tables SQL

```sql
-- Credentials table with encrypted storage
CREATE TABLE credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL CHECK (type IN ('jira', 'heretto', 'gemini', 'openai', 'anthropic')),
    name VARCHAR(255) NOT NULL,
    encrypted_data BYTEA NOT NULL,  -- AES-256 encrypted JSON
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, type, name)
);

-- Jobs table for tracking generation requests
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    instruction_set_id UUID REFERENCES instruction_sets(id),
    jql_query TEXT NOT NULL,
    additional_instructions TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    triggered_by VARCHAR(50) NOT NULL CHECK (triggered_by IN ('manual', 'webhook', 'scheduled')),
    output_filename VARCHAR(255),
    heretto_folder_id VARCHAR(255),
    auto_publish BOOLEAN DEFAULT false,
    tickets_processed INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Instruction sets for customizable prompts
CREATE TABLE instruction_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    system_prompt TEXT NOT NULL,
    user_instructions TEXT,
    dita_template_id UUID REFERENCES dita_templates(id),
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Webhook configurations
CREATE TABLE webhook_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    trigger_events TEXT[] NOT NULL,  -- Array of Jira event types
    jql_filter TEXT,  -- Optional JQL to filter which issues trigger
    instruction_set_id UUID NOT NULL REFERENCES instruction_sets(id),
    auto_publish BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    secret_token VARCHAR(255) NOT NULL,  -- For webhook signature verification
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_jobs_user_status ON jobs(user_id, status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX idx_credentials_user_type ON credentials(user_id, type);
CREATE INDEX idx_webhook_configs_active ON webhook_configs(is_active) WHERE is_active = true;
```

---

## 5. API Specifications

### 5.1 REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Authentication** | | |
| POST | `/api/v1/auth/login` | User login, returns JWT |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Invalidate refresh token |
| **Credentials** | | |
| GET | `/api/v1/credentials` | List all credentials for user |
| POST | `/api/v1/credentials` | Create new credential |
| PUT | `/api/v1/credentials/{id}` | Update credential |
| DELETE | `/api/v1/credentials/{id}` | Delete credential |
| POST | `/api/v1/credentials/{id}/test` | Test credential connection |
| **Instructions** | | |
| GET | `/api/v1/instructions` | List instruction sets |
| POST | `/api/v1/instructions` | Create instruction set |
| GET | `/api/v1/instructions/{id}` | Get instruction set details |
| PUT | `/api/v1/instructions/{id}` | Update instruction set |
| DELETE | `/api/v1/instructions/{id}` | Delete instruction set |
| **Jobs** | | |
| GET | `/api/v1/jobs` | List jobs with filtering/pagination |
| POST | `/api/v1/jobs` | Create and queue new job |
| GET | `/api/v1/jobs/{id}` | Get job details and status |
| POST | `/api/v1/jobs/{id}/cancel` | Cancel pending/running job |
| GET | `/api/v1/jobs/{id}/artifacts` | Get job output artifacts |
| POST | `/api/v1/jobs/{id}/retry` | Retry failed job |
| **Jira** | | |
| POST | `/api/v1/jira/preview` | Preview JQL query results |
| GET | `/api/v1/jira/projects` | List accessible projects |
| GET | `/api/v1/jira/versions/{project}` | List versions for project |
| **Webhooks** | | |
| GET | `/api/v1/webhooks` | List webhook configurations |
| POST | `/api/v1/webhooks` | Create webhook config |
| PUT | `/api/v1/webhooks/{id}` | Update webhook config |
| DELETE | `/api/v1/webhooks/{id}` | Delete webhook config |
| POST | `/api/v1/webhooks/jira` | Jira webhook receiver endpoint |
| **Heretto** | | |
| GET | `/api/v1/heretto/folders` | List available folders |
| POST | `/api/v1/heretto/validate` | Validate DITA content |

### 5.2 WebSocket Events

```typescript
// WebSocket event types for real-time updates
interface WebSocketEvents {
  // Server -> Client
  'job:status_changed': {
    jobId: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress?: number;
    message?: string;
  };
  
  'job:progress': {
    jobId: string;
    stage: 'extracting' | 'generating' | 'validating' | 'publishing';
    current: number;
    total: number;
    message: string;
  };
  
  'job:completed': {
    jobId: string;
    artifacts: Array<{
      id: string;
      filename: string;
      type: string;
    }>;
    herettoUrl?: string;
  };
  
  'job:error': {
    jobId: string;
    error: string;
    recoverable: boolean;
  };
}
```

---

## 6. DITA Generation

### 6.1 DITA Topic Template

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="release-notes-{version}">
  <title>Release Notes - Version {version}</title>
  <shortdesc>{short_description}</shortdesc>
  
  <prolog>
    <metadata>
      <keywords>
        <keyword>release notes</keyword>
        <keyword>{product}</keyword>
        <keyword>{version}</keyword>
      </keywords>
    </metadata>
  </prolog>
  
  <body>
    <section id="overview">
      <title>Overview</title>
      <p>{overview_content}</p>
    </section>
    
    <section id="new-features">
      <title>New Features</title>
      <ul>
        <!-- Generated feature list -->
      </ul>
    </section>
    
    <section id="improvements">
      <title>Improvements</title>
      <ul>
        <!-- Generated improvements list -->
      </ul>
    </section>
    
    <section id="bug-fixes">
      <title>Bug Fixes</title>
      <ul>
        <!-- Generated bug fixes list -->
      </ul>
    </section>
    
    <section id="known-issues">
      <title>Known Issues</title>
      <ul>
        <!-- Generated known issues list -->
      </ul>
    </section>
  </body>
</topic>
```

### 6.2 AI Prompt Template

```
You are a technical writer creating release notes in DITA XML format.

## Context
Product: {product_name}
Version: {version}
Release Date: {release_date}

## Instructions
{user_instructions}

## Jira Tickets
{formatted_tickets}

## Requirements
1. Generate valid DITA 1.3 XML
2. Categorize items as: New Features, Improvements, Bug Fixes, or Known Issues
3. Write clear, user-facing descriptions (not internal jargon)
4. Include ticket references where appropriate
5. Maintain consistent tone and style
6. Focus on user impact and benefits

## Output Format
Return only valid DITA XML content for the body sections. Do not include XML declaration or DOCTYPE.
```

---

## 7. Security Considerations

### 7.1 Credential Security

- All credentials encrypted at rest using AES-256-GCM
- Encryption keys stored in environment variables or secrets manager
- API tokens never logged or exposed in responses
- Credential access audited

### 7.2 API Security

- JWT-based authentication with short-lived access tokens (15 min)
- Refresh tokens stored securely with rotation
- Rate limiting on all endpoints
- Input validation and sanitization
- CORS configuration for frontend origin only

### 7.3 Webhook Security

- Signature verification for all incoming webhooks
- IP allowlisting for Jira webhook sources (optional)
- Webhook secret rotation capability
- Request payload validation

---

## 8. Development Phases

### Phase 1: Foundation (Weeks 1-3)

**Objective:** Establish core infrastructure and basic connectivity

| Task | Duration | Dependencies |
|------|----------|--------------|
| Set up Python backend project structure | 2 days | None |
| Configure FastAPI with async support | 1 day | Backend structure |
| Set up PostgreSQL and Redis | 1 day | None |
| Implement user authentication (JWT) | 3 days | Database |
| Create credential storage with encryption | 2 days | Authentication |
| Set up Angular project with Material UI | 2 days | None |
| Implement login/registration UI | 2 days | Angular setup |
| Create credential management UI | 3 days | Login UI |
| Basic Jira API integration | 2 days | Credentials |
| Unit tests for core services | 2 days | All above |

**Deliverables:**
- Working authentication system
- Secure credential storage for Jira
- Basic Jira connectivity verification

### Phase 2: AI Integration (Weeks 4-5)

**Objective:** Implement AI service layer with Gemini integration

| Task | Duration | Dependencies |
|------|----------|--------------|
| Design AI service interface | 1 day | None |
| Implement Gemini adapter | 2 days | AI interface |
| Create prompt template system | 2 days | Gemini adapter |
| Build instruction set management (backend) | 2 days | Database |
| Build instruction set management (frontend) | 3 days | Backend ready |
| Implement basic DITA generation | 2 days | AI integration |
| Add DITA validation | 1 day | DITA generation |
| Integration tests | 2 days | All above |

**Deliverables:**
- Working Gemini integration
- Customizable instruction sets
- Basic DITA output generation

### Phase 3: Job Processing (Weeks 6-7)

**Objective:** Build async job processing system

| Task | Duration | Dependencies |
|------|----------|--------------|
| Set up Celery with Redis | 1 day | Redis configured |
| Implement job orchestrator | 3 days | Celery setup |
| Create job status tracking | 2 days | Orchestrator |
| Build job queue UI | 2 days | Backend jobs API |
| Implement WebSocket for real-time updates | 2 days | Job tracking |
| Add job history and artifacts storage | 2 days | Jobs complete |
| Error handling and retry logic | 2 days | Job processing |

**Deliverables:**
- Async job processing
- Real-time status updates
- Job history and artifact management

### Phase 4: Heretto Integration (Weeks 8-9)

**Objective:** Complete Heretto CCMS integration

| Task | Duration | Dependencies |
|------|----------|--------------|
| Heretto API client implementation | 2 days | None |
| Heretto credential management | 1 day | Credential system |
| Folder browsing and selection | 2 days | Heretto client |
| Document upload workflow | 2 days | Folder selection |
| Upload status tracking | 1 day | Upload workflow |
| Heretto UI components | 2 days | Backend ready |
| End-to-end testing | 2 days | All above |

**Deliverables:**
- Full Heretto CCMS integration
- Automated publishing workflow
- Document management UI

### Phase 5: Webhook & Polish (Weeks 10-11)

**Objective:** Implement webhooks and production readiness

| Task | Duration | Dependencies |
|------|----------|--------------|
| Jira webhook endpoint | 2 days | Job orchestrator |
| Webhook configuration UI | 2 days | Webhook backend |
| Webhook signature verification | 1 day | Webhook endpoint |
| Dashboard with analytics | 2 days | Job history |
| Error reporting and notifications | 2 days | All systems |
| Performance optimization | 2 days | All systems |
| Documentation | 2 days | All features |
| Security audit | 1 day | All systems |

**Deliverables:**
- Working webhook integration
- Production-ready application
- Complete documentation

---

## 9. Testing Strategy

### 9.1 Unit Testing

- **Backend:** pytest with async support, 80%+ coverage target
- **Frontend:** Jest + Angular Testing Library
- Focus areas: AI service adapters, DITA validation, credential encryption

### 9.2 Integration Testing

- API endpoint testing with test database
- Jira/Heretto integration tests with mock servers
- WebSocket connection testing

### 9.3 End-to-End Testing

- Cypress for frontend E2E tests
- Complete workflow testing: Jira → AI → DITA → Heretto

### 9.4 Security Testing

- OWASP ZAP scanning
- Credential handling audit
- Penetration testing before production

---

## 10. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer (nginx)                     │
│                     SSL Termination / Rate Limiting              │
└─────────────────────────────────────────────────────────────────┘
                    │                           │
                    ▼                           ▼
    ┌──────────────────────────┐   ┌──────────────────────────┐
    │   Angular Frontend       │   │   FastAPI Backend        │
    │   (nginx container)      │   │   (gunicorn + uvicorn)   │
    │                          │   │   - Multiple workers     │
    │   - Static file serving  │   │   - Auto-scaling         │
    │   - SPA routing          │   │                          │
    └──────────────────────────┘   └──────────────────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────┐
                    │                          │                  │
                    ▼                          ▼                  ▼
    ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────┐
    │   PostgreSQL         │   │   Redis              │   │   Celery     │
    │   (managed service)  │   │   (managed service)  │   │   Workers    │
    │                      │   │                      │   │   (2-4 pods) │
    └──────────────────────┘   └──────────────────────┘   └──────────────┘
```

### 10.1 Environment Configuration

| Environment | Purpose | AI Model | Database |
|-------------|---------|----------|----------|
| Development | Local development | Gemini Flash | Local PostgreSQL |
| Staging | Integration testing | Gemini Pro | Managed PostgreSQL |
| Production | Live system | Gemini Pro | Managed PostgreSQL (HA) |

---

## 11. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Gemini API rate limits | Medium | High | Implement queuing, caching, and backoff |
| DITA validation failures | Medium | Medium | Pre-validation, template refinement |
| Jira API changes | Low | Medium | Version pinning, abstraction layer |
| Heretto API availability | Low | High | Retry logic, offline queue |
| Credential exposure | Low | Critical | Encryption, audit logging, rotation |
| AI hallucination in content | Medium | Medium | Human review workflow, validation |

---

## 12. Future Enhancements

### 12.1 Version 2.0 Candidates

- Additional AI model support (OpenAI GPT-4, Claude)
- Batch processing for multiple release versions
- Custom DITA topic types beyond release notes
- Integration with additional CCMS platforms
- Scheduled job execution
- Team collaboration features
- Content diff and versioning
- Analytics and reporting dashboard

### 12.2 Model Abstraction for Future Providers

The AI service interface is designed to easily accommodate additional providers:

```python
# Future adapter implementations
class OpenAIAdapter(AIServiceInterface):
    """OpenAI GPT-4 implementation"""
    pass

class ClaudeAdapter(AIServiceInterface):
    """Anthropic Claude implementation"""
    pass

# Factory for model selection
class AIServiceFactory:
    @staticmethod
    def create(provider: str, api_key: str, model: str) -> AIServiceInterface:
        adapters = {
            "gemini": GeminiAdapter,
            "openai": OpenAIAdapter,
            "anthropic": ClaudeAdapter,
        }
        return adapters[provider](api_key=api_key, model_name=model)
```

---

## 13. Estimated Timeline & Resources

### 13.1 Timeline Summary

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Foundation | 3 weeks | Week 3 |
| Phase 2: AI Integration | 2 weeks | Week 5 |
| Phase 3: Job Processing | 2 weeks | Week 7 |
| Phase 4: Heretto Integration | 2 weeks | Week 9 |
| Phase 5: Webhook & Polish | 2 weeks | Week 11 |
| **Total** | **11 weeks** | |

### 13.2 Resource Requirements

| Role | FTE | Duration |
|------|-----|----------|
| Backend Developer (Python) | 1 | 11 weeks |
| Frontend Developer (Angular) | 1 | 9 weeks |
| DevOps Engineer | 0.5 | 11 weeks |
| QA Engineer | 0.5 | 6 weeks |
| Technical Writer (Testing) | 0.25 | 4 weeks |

### 13.3 Infrastructure Costs (Monthly Estimate)

| Service | Development | Production |
|---------|-------------|------------|
| Cloud Compute | $100 | $400 |
| Managed PostgreSQL | $50 | $200 |
| Managed Redis | $30 | $100 |
| Google AI Studio (Gemini) | $50 | $200-500 |
| **Total** | **~$230/mo** | **~$900-1200/mo** |

---

## Appendix A: Environment Variables

```bash
# Application
APP_ENV=production
APP_SECRET_KEY=<random-256-bit-key>
APP_DEBUG=false

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379/0

# Authentication
JWT_SECRET_KEY=<random-256-bit-key>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Encryption (for credentials)
ENCRYPTION_KEY=<random-256-bit-key>

# Google AI Studio
GOOGLE_AI_API_KEY=<your-api-key>
GOOGLE_AI_MODEL=gemini-1.5-pro

# Jira (defaults, can be overridden per-user)
JIRA_WEBHOOK_SECRET=<webhook-secret>

# Heretto
HERETTO_BASE_URL=https://api.heretto.com
```

---

## Appendix B: API Response Examples

### Create Job Request

```json
POST /api/v1/jobs
{
  "jqlQuery": "project = PROD AND fixVersion = '2.0.0' AND status = Done",
  "instructionSetId": "uuid-of-instruction-set",
  "additionalInstructions": "Focus on customer-facing changes only",
  "outputFilename": "release-notes-v2.0.0.dita",
  "publishToHeretto": true,
  "herettoFolderId": "folder-uuid"
}
```

### Job Status Response

```json
{
  "id": "job-uuid",
  "status": "running",
  "progress": {
    "stage": "generating",
    "current": 15,
    "total": 23,
    "message": "Generating release notes content..."
  },
  "ticketsProcessed": 15,
  "createdAt": "2025-01-15T10:30:00Z",
  "startedAt": "2025-01-15T10:30:05Z"
}
```

---

*Document Version: 1.0*  
*Last Updated: December 2024*
