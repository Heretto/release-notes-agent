from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

from app.models.database import get_db, User, InstructionSet
from app.models.schemas import (
    InstructionSetCreate,
    InstructionSetUpdate,
    InstructionSetResponse
)
from app.api.dependencies import get_current_active_user, get_current_active_user_with_org, CurrentUserContext

router = APIRouter(prefix="/instructions")

@router.get("/", response_model=List[InstructionSetResponse])
async def list_instruction_sets(
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """List all instruction sets for current organization."""
    instruction_sets = db.query(InstructionSet).filter(
        InstructionSet.organization_id == context.organization_id
    ).all()
    return instruction_sets

@router.post("/", response_model=InstructionSetResponse)
async def create_instruction_set(
    instruction_data: InstructionSetCreate,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Create new instruction set."""
    # If setting as default, unset other defaults in organization
    if instruction_data.is_default:
        db.query(InstructionSet).filter(
            InstructionSet.organization_id == context.organization_id,
            InstructionSet.is_default == True
        ).update({"is_default": False})
    
    new_instruction = InstructionSet(
        user_id=context.user.id,
        organization_id=context.organization_id,
        **instruction_data.model_dump()
    )
    
    db.add(new_instruction)
    db.commit()
    db.refresh(new_instruction)
    
    return new_instruction

@router.get("/{instruction_id}", response_model=InstructionSetResponse)
async def get_instruction_set(
    instruction_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Get specific instruction set."""
    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == instruction_id,
        InstructionSet.organization_id == context.organization_id
    ).first()
    
    if not instruction_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction set not found"
        )
    
    return instruction_set

@router.put("/{instruction_id}", response_model=InstructionSetResponse)
async def update_instruction_set(
    instruction_id: UUID,
    instruction_data: InstructionSetUpdate,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Update instruction set."""
    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == instruction_id,
        InstructionSet.organization_id == context.organization_id
    ).first()
    
    if not instruction_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction set not found"
        )
    
    # If setting as default, unset other defaults in organization
    if instruction_data.is_default and not instruction_set.is_default:
        db.query(InstructionSet).filter(
            InstructionSet.organization_id == context.organization_id,
            InstructionSet.is_default == True
        ).update({"is_default": False})
    
    # Update fields — whitelist to prevent overwriting sensitive attributes
    _INSTRUCTION_UPDATABLE_FIELDS = {
        "name", "description", "jql_query", "system_prompt",
        "user_instructions", "dita_template_id", "heretto_folder_id",
        "publish_to_heretto", "is_default",
    }
    for field, value in instruction_data.model_dump(exclude_unset=True).items():
        if field in _INSTRUCTION_UPDATABLE_FIELDS:
            setattr(instruction_set, field, value)
    
    db.commit()
    db.refresh(instruction_set)
    
    return instruction_set

@router.delete("/{instruction_id}")
async def delete_instruction_set(
    instruction_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Delete instruction set."""
    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == instruction_id,
        InstructionSet.organization_id == context.organization_id
    ).first()
    
    if not instruction_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction set not found"
        )
    
    db.delete(instruction_set)
    db.commit()
    
    return {"message": "Instruction set deleted successfully"}

class TestQueryRequest(BaseModel):
    credential_id: UUID

@router.post("/{instruction_id}/test")
async def test_instruction_query(
    instruction_id: UUID,
    request: TestQueryRequest,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Test the JQL query from an instruction set."""
    from app.services.jira_service_v3 import JiraServiceV3
    from app.models.database import Credential, CredentialType
    from app.core.security import decrypt_credentials
    import asyncio
    
    # Get the instruction set
    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == instruction_id,
        InstructionSet.organization_id == context.organization_id
    ).first()
    
    if not instruction_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction set not found"
        )
    
    # Get Jira credentials - use the provided credential_id from request
    jira_credential = db.query(Credential).filter(
        Credential.id == request.credential_id,
        Credential.organization_id == context.organization_id,
        Credential.type == CredentialType.JIRA
    ).first()
    
    if not jira_credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Jira credentials configured. Please add Jira credentials first."
        )
    
    # Decrypt credentials
    decrypted = decrypt_credentials(jira_credential.encrypted_data)
    
    # Initialize Jira service
    jira_service = JiraServiceV3(
        server=decrypted["server_url"],
        email=decrypted["email"],
        api_token=decrypted["api_token"]
    )
    
    try:
        # Test the JQL query with a limited number of results
        issues = await jira_service.execute_query(
            jql=instruction_set.jql_query,
            max_results=10  # Limit to 10 for testing
        )
        
        # Format the response
        return {
            "success": True,
            "instruction_set": {
                "name": instruction_set.name,
                "jql_query": instruction_set.jql_query
            },
            "jira_credential": {
                "name": jira_credential.name,
                "server": decrypted["server_url"]
            },
            "results": {
                "total_found": len(issues),
                "limited_to": 10,
                "issues": [
                    {
                        "key": issue.key,
                        "summary": issue.summary,
                        "type": issue.issue_type,
                        "status": issue.status,
                        "priority": issue.priority,
                        "created": issue.created_at if hasattr(issue, 'created_at') else None,
                        "labels": issue.labels,
                        "components": issue.components
                    }
                    for issue in issues
                ]
            },
            "message": f"Successfully retrieved {len(issues)} issues (limited to 10 for testing)"
        }
    except Exception as e:
        logger.error("JQL query test failed for instruction set %s: %s", instruction_set.id, e, exc_info=True)
        return {
            "success": False,
            "instruction_set": {
                "name": instruction_set.name,
                "jql_query": instruction_set.jql_query
            },
            "message": "Failed to execute JQL query — check your query syntax and Jira credentials"
        }