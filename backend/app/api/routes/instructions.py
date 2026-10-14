"""Instruction sets: the query, the agents by role, and the pipeline's guidance."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

from app.models.database import get_db, InstructionSet, Agent, Credential, CredentialType
from app.models.schemas import (
    InstructionSetCreate,
    InstructionSetUpdate,
    InstructionSetResponse
)
from app.api.dependencies import get_current_active_user_with_org, CurrentUserContext

router = APIRouter(prefix="/instructions")

_INSTRUCTION_UPDATABLE_FIELDS = {
    "name", "description", "jql_query", "jira_credential_id",
    "dita_template_id", "heretto_folder_id",
    "publish_to_heretto", "is_default",
    "writer_agent_id", "analysis_agent_id", "product_name",
    "relevance_guidance", "organization_guidance", "chunking_strategy",
}


def _to_response(instruction_set: InstructionSet) -> InstructionSetResponse:
    return InstructionSetResponse(
        id=instruction_set.id,
        user_id=instruction_set.user_id,
        name=instruction_set.name,
        description=instruction_set.description,
        jql_query=instruction_set.jql_query,
        jira_credential_id=instruction_set.jira_credential_id,
        dita_template_id=instruction_set.dita_template_id,
        heretto_folder_id=instruction_set.heretto_folder_id,
        publish_to_heretto=bool(instruction_set.publish_to_heretto),
        is_default=bool(instruction_set.is_default),
        writer_agent_id=instruction_set.writer_agent_id,
        analysis_agent_id=instruction_set.analysis_agent_id,
        writer_agent_name=instruction_set.writer_agent.name if instruction_set.writer_agent else None,
        analysis_agent_name=instruction_set.analysis_agent.name if instruction_set.analysis_agent else None,
        product_name=instruction_set.product_name,
        relevance_guidance=instruction_set.relevance_guidance,
        organization_guidance=instruction_set.organization_guidance,
        chunking_strategy=instruction_set.chunking_strategy or "single",
        created_at=instruction_set.created_at,
        updated_at=instruction_set.updated_at,
    )


def _validate_agent_id(agent_id: Optional[UUID], organization_id: UUID, db: Session, role: str) -> None:
    """Raise 404 if the agent doesn't belong to this organization."""
    if agent_id is None:
        return
    found = db.query(Agent.id).filter(Agent.id == agent_id, Agent.organization_id == organization_id).first()
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{role.capitalize()} agent not found in organization: {agent_id}"
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


@router.get("", response_model=List[InstructionSetResponse])
async def list_instruction_sets(
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """List all instruction sets for current organization."""
    instruction_sets = db.query(InstructionSet).filter(
        InstructionSet.organization_id == context.organization_id
    ).order_by(InstructionSet.created_at).all()
    return [_to_response(i) for i in instruction_sets]


@router.post("", response_model=InstructionSetResponse)
async def create_instruction_set(
    instruction_data: InstructionSetCreate,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """Create new instruction set."""
    _validate_agent_id(instruction_data.writer_agent_id, context.organization_id, db, "writer")
    _validate_agent_id(instruction_data.analysis_agent_id, context.organization_id, db, "analysis")
    _validate_jira_credential_id(instruction_data.jira_credential_id, context.organization_id, db)

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
    return _to_response(new_instruction)


@router.get("/{instruction_id}", response_model=InstructionSetResponse)
async def get_instruction_set(
    instruction_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == instruction_id,
        InstructionSet.organization_id == context.organization_id
    ).first()
    if not instruction_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction set not found")
    return _to_response(instruction_set)


@router.put("/{instruction_id}", response_model=InstructionSetResponse)
async def update_instruction_set(
    instruction_id: UUID,
    instruction_data: InstructionSetUpdate,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == instruction_id,
        InstructionSet.organization_id == context.organization_id
    ).first()
    if not instruction_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction set not found")

    if instruction_data.is_default and not instruction_set.is_default:
        db.query(InstructionSet).filter(
            InstructionSet.organization_id == context.organization_id,
            InstructionSet.is_default == True
        ).update({"is_default": False})

    update_data = instruction_data.model_dump(exclude_unset=True)
    if "jira_credential_id" in update_data:
        _validate_jira_credential_id(update_data["jira_credential_id"], context.organization_id, db)
    if "writer_agent_id" in update_data:
        _validate_agent_id(update_data["writer_agent_id"], context.organization_id, db, "writer")
    if "analysis_agent_id" in update_data:
        _validate_agent_id(update_data["analysis_agent_id"], context.organization_id, db, "analysis")
    for field, value in update_data.items():
        if field in _INSTRUCTION_UPDATABLE_FIELDS:
            setattr(instruction_set, field, value)

    db.commit()
    db.refresh(instruction_set)
    return _to_response(instruction_set)


@router.delete("/{instruction_id}")
async def delete_instruction_set(
    instruction_id: UUID,
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == instruction_id,
        InstructionSet.organization_id == context.organization_id
    ).first()
    if not instruction_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction set not found")
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
    from app.core.security import decrypt_credentials

    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == instruction_id,
        InstructionSet.organization_id == context.organization_id
    ).first()
    if not instruction_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction set not found")

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

    decrypted = decrypt_credentials(jira_credential.encrypted_data)
    jira_service = JiraServiceV3(
        server=decrypted["server_url"],
        email=decrypted["email"],
        api_token=decrypted["api_token"]
    )

    try:
        issues = await jira_service.execute_query(jql=instruction_set.jql_query, max_results=10)
        return {
            "success": True,
            "instruction_set": {"name": instruction_set.name, "jql_query": instruction_set.jql_query},
            "jira_credential": {"name": jira_credential.name, "server": decrypted["server_url"]},
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
                        "created": issue.created,
                        "labels": issue.labels,
                        "components": issue.components,
                        "url": issue.url,
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
            "instruction_set": {"name": instruction_set.name, "jql_query": instruction_set.jql_query},
            "message": "Failed to execute JQL query — check your query syntax and Jira credentials"
        }
