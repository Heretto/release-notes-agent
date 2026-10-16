"""Instruction sets: the query, the agents by role, and the pipeline's guidance."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

from app.models.database import get_db, InstructionSet, Agent, Credential, CredentialType
from app.models.schemas import (
    InstructionSetCreate,
    InstructionSetUpdate,
    InstructionSetResponse,
    TopicLayout,
)
from app.services.jql_variables import defaults_of, normalize_specs, release_query, resolve as resolve_jql
from app.api.dependencies import get_current_active_user_with_org, CurrentUserContext

router = APIRouter(prefix="/instructions")

_INSTRUCTION_UPDATABLE_FIELDS = {
    "name", "description", "source_mode", "jira_project", "extra_jql",
    "jql_query", "variables", "jira_credential_id",
    "dita_template_id", "heretto_folder_id",
    "publish_to_heretto", "is_default",
    "writer_agent_id", "analysis_agent_id", "product_name",
    "relevance_guidance", "organization_guidance", "chunking_strategy", "layout",
}


def _to_response(instruction_set: InstructionSet) -> InstructionSetResponse:
    return InstructionSetResponse(
        id=instruction_set.id,
        user_id=instruction_set.user_id,
        name=instruction_set.name,
        description=instruction_set.description,
        source_mode=instruction_set.source_mode or "jql",
        jira_project=instruction_set.jira_project,
        extra_jql=instruction_set.extra_jql,
        jql_query=instruction_set.jql_query or "",
        variables=instruction_set.variables or {},
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
        layout=TopicLayout(**(instruction_set.layout or {})) if instruction_set.layout else TopicLayout(),
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

    fields = instruction_data.model_dump(mode="json")
    # Keep the specs keyed by the tokens the query actually contains, whatever was sent.
    fields["variables"] = normalize_specs(fields.get("jql_query") or "", fields.get("variables"))
    new_instruction = InstructionSet(
        user_id=context.user.id,
        organization_id=context.organization_id,
        **fields
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

    # mode="json" so nested models (layout) land on the JSON column as plain dicts.
    update_data = instruction_data.model_dump(exclude_unset=True, mode="json")
    if "jira_credential_id" in update_data:
        _validate_jira_credential_id(update_data["jira_credential_id"], context.organization_id, db)
    if "writer_agent_id" in update_data:
        _validate_agent_id(update_data["writer_agent_id"], context.organization_id, db, "writer")
    if "analysis_agent_id" in update_data:
        _validate_agent_id(update_data["analysis_agent_id"], context.organization_id, db, "analysis")
    for field, value in update_data.items():
        if field in _INSTRUCTION_UPDATABLE_FIELDS:
            setattr(instruction_set, field, value)

    # Either side moving can orphan a spec or leave a new token undescribed, so renormalize
    # against whatever the query now is.
    if "jql_query" in update_data or "variables" in update_data:
        instruction_set.variables = normalize_specs(
            instruction_set.jql_query or "", instruction_set.variables
        )

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


@router.get("/{instruction_id}/releases")
async def list_instruction_releases(
    instruction_id: UUID,
    start_at: int = Query(0, ge=0),
    max_results: int = Query(5, ge=1, le=50),
    context: CurrentUserContext = Depends(get_current_active_user_with_org),
    db: Session = Depends(get_db)
):
    """The Jira releases (fix versions) an instruction set in "releases" mode can run on.

    Read live from Jira rather than stored: a release list changes in Jira, not here, and a
    stale copy would offer a version that no longer exists.
    """
    from app.services.jira_service_v3 import JiraServiceV3
    from app.core.security import decrypt_credentials

    instruction_set = db.query(InstructionSet).filter(
        InstructionSet.id == instruction_id,
        InstructionSet.organization_id == context.organization_id
    ).first()
    if not instruction_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction set not found")

    project = (instruction_set.jira_project or "").strip()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This instruction set has no Jira project key"
        )

    jira_credential = _resolve_jira_credential(instruction_set, context.organization_id, db)
    decrypted = decrypt_credentials(jira_credential.encrypted_data)
    jira_service = JiraServiceV3(
        server=decrypted["server_url"],
        email=decrypted["email"],
        api_token=decrypted["api_token"]
    )

    try:
        page = await jira_service.get_versions(project, start_at=start_at, max_results=max_results)
    except Exception as exc:
        logger.error("Failed to list releases for instruction set %s: %s", instruction_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return {
        "project": project.upper(),
        "releases": page["releases"],
        "total": page["total"],
        "has_more": not page["is_last"],
        "next_start": page["next_start"],
    }


def _resolve_jira_credential(instruction_set: InstructionSet, organization_id: UUID, db: Session) -> Credential:
    """The instruction set's own Jira credential, or the organization's only one."""
    query = db.query(Credential).filter(
        Credential.organization_id == organization_id,
        Credential.type == CredentialType.JIRA,
    )
    if instruction_set.jira_credential_id:
        credential = query.filter(Credential.id == instruction_set.jira_credential_id).first()
    else:
        credentials = query.all()
        credential = credentials[0] if len(credentials) == 1 else None
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Jira credential is selected for this instruction set."
        )
    return credential


class TestQueryRequest(BaseModel):
    credential_id: UUID
    #: Values for the query's {name} variables. Anything omitted falls back to the
    #: variable's stored default, so a test can be run straight from the card.
    variables: Dict[str, str] = {}
    #: In "releases" mode, which Jira release to test against.
    release: Optional[str] = None


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

    # Resolve here rather than letting the browser send a built query: the same escaping
    # rule that protects a real run has to protect the test, or the test is testing
    # something else. See app/services/jql_variables.py.
    try:
        if (instruction_set.source_mode or "jql") == "releases":
            release = (request.release or "").strip()
            if not release:
                # A test is about the query shape, so the newest release is as good an
                # example as any — and it saves the dialog from having to pick one.
                newest = await jira_service.get_versions(
                    instruction_set.jira_project or "", start_at=0, max_results=1
                )
                versions = newest["releases"]
                if not versions:
                    raise ValueError(
                        f"No releases found in {(instruction_set.jira_project or '').upper()}"
                    )
                release = versions[0]["name"]
            resolved_jql = release_query(
                instruction_set.jira_project or "", release, instruction_set.extra_jql
            )
        else:
            values = {**defaults_of(instruction_set.variables or {})}
            values.update({name: (value or "").strip() for name, value in request.variables.items()})
            resolved_jql = resolve_jql(instruction_set.jql_query or "", values)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    try:
        issues = await jira_service.execute_query(jql=resolved_jql, max_results=10)
        return {
            "success": True,
            "instruction_set": {"name": instruction_set.name, "jql_query": resolved_jql},
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
            "instruction_set": {"name": instruction_set.name, "jql_query": resolved_jql},
            "message": "Failed to execute JQL query — check your query syntax and Jira credentials"
        }
