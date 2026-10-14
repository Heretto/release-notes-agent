from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

from app.models.database import get_db, User, InstructionSet, InstructionSetAgent, Agent, Credential, CredentialType
from app.models.schemas import (
    InstructionSetCreate,
    InstructionSetUpdate,
    InstructionSetResponse
)
from app.api.dependencies import get_current_active_user, get_current_active_user_with_org, CurrentUserContext

router = APIRouter(prefix="/instructions")


def _to_response(instruction_set: InstructionSet) -> InstructionSetResponse:
    """Build the response shape, reading agent_ids off the ordered agent_links relationship."""
    return InstructionSetResponse(
        id=instruction_set.id,
        user_id=instruction_set.user_id,
        name=instruction_set.name,
        description=instruction_set.description,
        jql_query=instruction_set.jql_query,
        jira_credential_id=instruction_set.jira_credential_id,
        dita_template_id=instruction_set.dita_template_id,
        heretto_folder_id=instruction_set.heretto_folder_id,
        publish_to_heretto=instruction_set.publish_to_heretto,
        is_default=instruction_set.is_default,
        agent_ids=[link.agent_id for link in instruction_set.agent_links],
        created_at=instruction_set.created_at,
        updated_at=instruction_set.updated_at,
    )


def _validate_agent_ids(agent_ids: List[UUID], organization_id: UUID, db: Session) -> None:
    """Raise 404 if any agent_id doesn't belong to this organization."""
    if not agent_ids:
        return
    found = db.query(Agent.id).filter(
        Agent.id.in_(agent_ids),
        Agent.organization_id == organization_id,
    ).all()
    found_ids = {row[0] for row in found}
    missing = [str(a) for a in agent_ids if a not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent(s) not found in organization: {', '.join(missing)}"
        )


def _validate_jira_credential_id(jira_credential_id, organization_id: UUID, db: Session) -> None:
    """Raise 404 if the Jira credential doesn't belong to this organization."""
    if jira_credential_id is None:
        return
    found = db.query(Credential.id).filter(
        Credential.id == jira_credential_id,
        Credential.organization_id == organization_id,
        Credential.type == CredentialType.JIRA,
    ).first()
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jira credential not found in organization: {jira_credential_id}"
        )


def _set_agent_links(instruction_set: InstructionSet, agent_ids: List[UUID], db: Session) -> None:
    """Replace the instruction set's agent chain wholesale, in the given order."""
    db.query(InstructionSetAgent).filter(
        InstructionSetAgent.instruction_set_id == instruction_set.id
    ).delete()
    for position, agent_id in enumerate(agent_ids):
        db.add(InstructionSetAgent(
            instruction_set_id=instruction_set.id,
            agent_id=agent_id,
            position=position,
        ))


@router.get("", response_model=List[InstructionSetResponse])
async def list_instruction_sets(
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """List all instruction sets for current organization."""
    instruction_sets = db.query(InstructionSet).filter(
        InstructionSet.organization_id == context.organization_id
    ).all()
    return [_to_response(i) for i in instruction_sets]

@router.post("", response_model=InstructionSetResponse)
async def create_instruction_set(
    instruction_data: InstructionSetCreate,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Create new instruction set."""
    _validate_agent_ids(instruction_data.agent_ids, context.organization_id, db)
    _validate_jira_credential_id(instruction_data.jira_credential_id, context.organization_id, db)

    # If setting as default, unset other defaults in organization
    if instruction_data.is_default:
        db.query(InstructionSet).filter(
            InstructionSet.organization_id == context.organization_id,
            InstructionSet.is_default == True
        ).update({"is_default": False})

    fields = instruction_data.model_dump(exclude={"agent_ids"})
    new_instruction = InstructionSet(
        user_id=context.user.id,
        organization_id=context.organization_id,
        **fields
    )

    db.add(new_instruction)
    db.flush()
    _set_agent_links(new_instruction, instruction_data.agent_ids, db)

    db.commit()
    db.refresh(new_instruction)

    return _to_response(new_instruction)

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

    return _to_response(instruction_set)

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
        "name", "description", "jql_query", "jira_credential_id",
        "dita_template_id", "heretto_folder_id",
        "publish_to_heretto", "is_default",
    }
    update_data = instruction_data.model_dump(exclude_unset=True)
    if "jira_credential_id" in update_data:
        _validate_jira_credential_id(update_data["jira_credential_id"], context.organization_id, db)
    for field, value in update_data.items():
        if field in _INSTRUCTION_UPDATABLE_FIELDS:
            setattr(instruction_set, field, value)

    if "agent_ids" in update_data:
        agent_ids = update_data["agent_ids"] or []
        _validate_agent_ids(agent_ids, context.organization_id, db)
        _set_agent_links(instruction_set, agent_ids, db)

    db.commit()
    db.refresh(instruction_set)

    return _to_response(instruction_set)

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