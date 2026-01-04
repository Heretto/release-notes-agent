from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.models.database import get_db, User, Job, JobArtifact, JobRequest, InstructionSet, Credential, CredentialType, JobStatus, JobTrigger
from app.models.schemas import (
    JobCreate,
    JobResponse,
    JobArtifactResponse,
    JiraPreviewRequest,
    JiraPreviewResponse,
    JobStatusEnum
)
from app.api.dependencies import get_current_active_user, get_current_active_user_with_org, CurrentUserContext
from app.services.job_orchestrator import JobOrchestrator
from app.core.security import decrypt_credentials

router = APIRouter(prefix="/jobs")

@router.get("/", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[JobStatusEnum] = None,
    limit: int = 50,
    offset: int = 0,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """List jobs with optional filtering."""
    query = db.query(Job).filter(Job.organization_id == context.organization_id)
    
    if status:
        query = query.filter(Job.status == status)
    
    jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
    return jobs

@router.post("/", response_model=JobResponse)
async def create_job(
    job_data: JobCreate,
    background_tasks: BackgroundTasks,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Create and queue new job."""
    # Verify instruction set exists in organization
    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == job_data.instruction_set_id,
        InstructionSet.organization_id == context.organization_id
    ).first()
    
    if not instruction_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction set not found"
        )
    
    # Verify AI credential if provided
    if job_data.ai_credential_id:
        ai_credential = db.query(Credential).filter(
            Credential.id == job_data.ai_credential_id,
            Credential.organization_id == context.organization_id,
            Credential.type.in_([CredentialType.GEMINI, CredentialType.OPENAI, CredentialType.ANTHROPIC])
        ).first()
        
        if not ai_credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI credential not found"
            )
    
    # Create job
    new_job = Job(
        user_id=context.user.id,
        organization_id=context.organization_id,
        instruction_set_id=job_data.instruction_set_id,
        ai_credential_id=job_data.ai_credential_id,
        jql_query=job_data.jql_query,
        additional_instructions=job_data.additional_instructions,
        output_filename=job_data.output_filename,
        heretto_folder_id=job_data.heretto_folder_id,
        auto_publish=job_data.publish_to_heretto,
        max_tickets=job_data.max_tickets,
        triggered_by="manual",
        status="pending"
    )
    
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # Queue job for processing
    orchestrator = JobOrchestrator(db)
    background_tasks.add_task(
        orchestrator.process_job,
        job_id=new_job.id
    )
    
    return new_job

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Get job details and status."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == context.organization_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job

@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Cancel pending or running job."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == context.organization_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status not in ["pending", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status}"
        )
    
    job.status = "cancelled"
    job.completed_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Job cancelled successfully"}

@router.get("/{job_id}/artifacts", response_model=List[JobArtifactResponse])
async def get_job_artifacts(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Get job output artifacts."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == context.organization_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    artifacts = db.query(JobArtifact).filter(
        JobArtifact.job_id == job_id
    ).all()
    
    return artifacts

@router.get("/{job_id}/requests")
async def get_job_requests(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Get job requests (API calls made during job execution)."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == context.organization_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    requests = db.query(JobRequest).filter(
        JobRequest.job_id == job_id
    ).order_by(JobRequest.created_at).all()
    
    # Format the requests for frontend display
    formatted_requests = []
    for req in requests:
        import json
        request_data = json.loads(req.request_data) if req.request_data else {}
        response_data = json.loads(req.response_data) if req.response_data else {}
        
        formatted_requests.append({
            "id": str(req.id),
            "type": req.request_type,
            "status": req.status,
            "timestamp": req.created_at.isoformat(),
            "duration_ms": req.duration_ms,
            "error_message": req.error_message,
            "request_data": request_data,
            "response_data": response_data
        })
    
    return formatted_requests

@router.get("/{job_id}/artifacts/{artifact_id}/content")
async def get_artifact_content(
    job_id: UUID,
    artifact_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Get artifact content."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == context.organization_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    artifact = db.query(JobArtifact).filter(
        JobArtifact.id == artifact_id,
        JobArtifact.job_id == job_id
    ).first()
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    return {
        "filename": artifact.filename,
        "content": artifact.content,
        "content_type": "application/xml" if (artifact.artifact_type == "dita" or artifact.filename.endswith(".dita")) else "text/plain"
    }

@router.get("/{job_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    job_id: UUID,
    artifact_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Download artifact as file."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == context.organization_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    artifact = db.query(JobArtifact).filter(
        JobArtifact.id == artifact_id,
        JobArtifact.job_id == job_id
    ).first()
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    # Determine content type based on file extension and artifact type
    if artifact.artifact_type == "dita" or artifact.filename.endswith((".xml", ".dita")):
        content_type = "application/xml"
    elif artifact.artifact_type in ["ai_log", "validation_error", "warning", "debug"] or artifact.filename.endswith(".log"):
        content_type = "text/plain"
    else:
        content_type = "text/plain"
    
    # Return the file as a downloadable response
    return Response(
        content=artifact.content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"'
        }
    )

@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Retry failed job."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == context.organization_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only retry failed jobs"
        )
    
    # Reset job status
    job.status = "pending"
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    db.commit()
    
    # Queue job for processing
    orchestrator = JobOrchestrator(db)
    background_tasks.add_task(
        orchestrator.process_job,
        job_id=job.id
    )
    
    return job

@router.delete("/{job_id}/artifacts")
async def delete_all_job_artifacts(
    job_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Delete all artifacts for a specific job."""
    # Verify job ownership
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == context.organization_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Delete all artifacts for this job
    deleted_count = db.query(JobArtifact).filter(
        JobArtifact.job_id == job_id
    ).delete()
    
    db.commit()
    
    return {
        "message": f"Successfully deleted {deleted_count} artifacts",
        "job_id": str(job_id),
        "deleted_count": deleted_count
    }

@router.delete("/{job_id}/artifacts/{artifact_id}")
async def delete_job_artifact(
    job_id: UUID,
    artifact_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Delete a specific artifact."""
    # Verify job ownership
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == context.organization_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Find and delete the specific artifact
    artifact = db.query(JobArtifact).filter(
        JobArtifact.id == artifact_id,
        JobArtifact.job_id == job_id
    ).first()
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    artifact_filename = artifact.filename
    db.delete(artifact)
    db.commit()
    
    return {
        "message": f"Successfully deleted artifact: {artifact_filename}",
        "artifact_id": str(artifact_id),
        "filename": artifact_filename
    }

@router.post("/preview", response_model=JiraPreviewResponse)
async def preview_jira_query(
    preview_request: JiraPreviewRequest,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Preview JQL query results."""
    # Get Jira credential
    credential = db.query(Credential).filter(
        Credential.id == preview_request.credential_id,
        Credential.organization_id == context.organization_id,
        Credential.type == "jira"
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jira credential not found"
        )
    
    # Decrypt and use credential
    from app.services.jira_service import JiraService
    decrypted = decrypt_credentials(credential.encrypted_data)
    
    jira_service = JiraService(
        server=decrypted["server_url"],
        email=decrypted["email"],
        api_token=decrypted["api_token"]
    )
    
    try:
        tickets = await jira_service.execute_query(
            jql=preview_request.jql_query,
            max_results=10  # Limit preview results
        )
        
        return JiraPreviewResponse(
            count=len(tickets),
            tickets=tickets
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"JQL query failed: {str(e)}"
        )

@router.post("/{job_id}/rerun", response_model=JobResponse)
async def rerun_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Rerun a job with the same parameters."""
    # Get the original job
    original_job = db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == context.organization_id
    ).first()
    
    if not original_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Create a new job with the same parameters
    new_job = Job(
        user_id=context.user.id,
        organization_id=context.organization_id,
        instruction_set_id=original_job.instruction_set_id,
        ai_credential_id=original_job.ai_credential_id,
        jql_query=original_job.jql_query,
        additional_instructions=original_job.additional_instructions,
        status=JobStatus.PENDING,
        triggered_by=JobTrigger.MANUAL,  # Rerun is always manual
        output_filename=original_job.output_filename,
        heretto_folder_id=original_job.heretto_folder_id,
        auto_publish=original_job.auto_publish,
        max_tickets=original_job.max_tickets
    )
    
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # Schedule the job for processing
    from app.services.job_orchestrator import JobOrchestrator
    orchestrator = JobOrchestrator(db)
    background_tasks.add_task(orchestrator.process_job, new_job.id)
    
    return JobResponse(
        id=new_job.id,
        user_id=new_job.user_id,
        instruction_set_id=new_job.instruction_set_id,
        ai_credential_id=new_job.ai_credential_id,
        jql_query=new_job.jql_query,
        additional_instructions=new_job.additional_instructions,
        status=new_job.status,
        triggered_by=new_job.triggered_by,
        output_filename=new_job.output_filename,
        heretto_folder_id=new_job.heretto_folder_id,
        auto_publish=new_job.auto_publish,
        tickets_processed=new_job.tickets_processed,
        max_tickets=new_job.max_tickets,
        error_message=new_job.error_message,
        created_at=new_job.created_at,
        started_at=new_job.started_at,
        completed_at=new_job.completed_at
    )