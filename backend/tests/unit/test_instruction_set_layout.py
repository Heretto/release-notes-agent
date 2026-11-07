"""An instruction set's topic layout has to survive the round trip through the API.

The response schema once lacked a ``layout`` field, so Pydantic dropped it silently: the
editor loaded the defaults, and the next save wrote them over what had been stored.
"""
import uuid
from datetime import datetime
from types import SimpleNamespace

from app.api.routes.instructions import _to_response
from app.models.schemas import InstructionSetCreate


AGENT_LAYOUT = {
    "mode": "agent",
    "guidance": "One bold paragraph per product, then its notes as a list.",
}


def _stored_set(layout):
    return SimpleNamespace(
        id=uuid.uuid4(), user_id=uuid.uuid4(), name="Set", description=None,
        source_mode="jql", jira_project=None, extra_jql=None, jql_query="project = X",
        variables={}, jira_credential_id=None, dita_template_id=None,
        heretto_folder_id=None, heretto_credential_id=None, publish_to_heretto=False,
        is_default=False, writer_agent_id=None, analysis_agent_id=None,
        writer_agent=None, analysis_agent=None, product_name=None,
        relevance_guidance=None, chunking_strategy="single",
        layout=layout, created_at=datetime.now(), updated_at=None,
    )


def test_response_carries_the_stored_layout():
    body = _to_response(_stored_set(AGENT_LAYOUT)).model_dump(mode="json")
    assert body["layout"]["mode"] == "agent"
    assert body["layout"]["guidance"] == AGENT_LAYOUT["guidance"]


def test_create_keeps_the_layout_it_was_sent():
    fields = InstructionSetCreate(
        name="Set", jql_query="project = X", layout=AGENT_LAYOUT
    ).model_dump(mode="json")
    assert fields["layout"]["mode"] == "agent"
    assert fields["layout"]["guidance"] == AGENT_LAYOUT["guidance"]
