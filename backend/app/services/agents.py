"""Resolving an instruction set's agents into something the pipeline can run.

A hop-core agent row carries the persona and references; the AI configuration it points at
carries the (encrypted) key and the model. This module turns a row into a ready
``AgentRunner`` and reports a person-readable reason when it cannot.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from hop_core.agents import AgentDefinition, AgentRequest, AgentRunResult, AgentRunner
from hop_core.agents.providers import CredentialAiService
from hop_core.agents.references import heretto_reference_source
from hop_core.models.agent import Agent

from app.core.security import decrypt_credentials

logger = logging.getLogger(__name__)


class AgentUnavailable(Exception):
    """The agent cannot run; the message is safe to show a person."""


@dataclass
class ResolvedAgent:
    role: str
    row: Agent
    definition: AgentDefinition
    service: CredentialAiService
    runner: AgentRunner

    @property
    def name(self) -> str:
        return self.row.name

    async def run(
        self,
        instructions: str,
        input_text: str = "",
        max_tokens: Optional[int] = 4096,
        temperature: Optional[float] = None,
    ) -> AgentRunResult:
        return await self.runner.run(
            self.definition,
            AgentRequest(instructions=instructions, input=input_text, max_tokens=max_tokens, temperature=temperature),
        )


def resolve_agent(db: Session, agent_row: Optional[Agent], organization_id: Optional[UUID], role: str) -> ResolvedAgent:
    """Build a runnable agent, or raise AgentUnavailable with the reason."""
    if agent_row is None:
        raise AgentUnavailable(
            f"The instruction set has no {role} agent. Pick one in the instruction set before running a job."
        )
    if organization_id is not None and agent_row.organization_id != organization_id:
        raise AgentUnavailable(f"The {role} agent '{agent_row.name}' belongs to another organization.")
    if not agent_row.is_active:
        raise AgentUnavailable(f"The {role} agent '{agent_row.name}' is inactive. Activate it in the Agents page.")

    credential = agent_row.ai_configuration
    if credential is None:
        raise AgentUnavailable(
            f"Agent '{agent_row.name}' has no AI configuration selected. "
            "Configure one in the Agents page before running this job."
        )
    try:
        payload = decrypt_credentials(credential.encrypted_data)
    except Exception:
        raise AgentUnavailable(
            f"Failed to decrypt the AI configuration for agent '{agent_row.name}'. It may need to be re-created."
        )

    definition = AgentDefinition.from_model(agent_row)
    service = CredentialAiService.from_credential(
        credential,
        api_key=payload.get("api_key", ""),
        model=payload.get("model") or definition.ai_configuration.model if definition.ai_configuration else "",
    )
    reference_source = heretto_reference_source(organization_id, db) if organization_id else None
    runner = AgentRunner(service, reference_source=reference_source)
    return ResolvedAgent(role=role, row=agent_row, definition=definition, service=service, runner=runner)
