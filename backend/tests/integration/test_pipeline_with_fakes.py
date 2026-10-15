"""The pipeline end to end against the local database, with fake Jira and fake agents.

Runs a job twice: the first run drafts notes from three issues (one of which is not
user-facing); the rerun sees one issue changed, one removed and one added, and must leave the
unchanged note alone, rewrite the changed one with history, flag the one whose issue left the
query, and draft the new one.

Needs the development Postgres from docker-compose (skipped when it is not reachable).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Dict, List

import pytest
from sqlalchemy import text

from app.config import get_settings
from app.models.schemas import JiraTicket

try:
    from hop_core.db import get_engine, get_session_factory, init_engine
    init_engine(get_settings().database_url)
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    DB_AVAILABLE = True
except Exception:  # pragma: no cover - environment-dependent
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="development database is not reachable")


# ── Fakes ────────────────────────────────────────────────────────────────────────────

def _ticket(key: str, summary: str, description: str = "", status: str = "Done", issue_type: str = "Story",
            components=None, comments=None) -> JiraTicket:
    return JiraTicket(
        key=key, summary=summary, description=description, issue_type=issue_type, status=status, priority="High",
        labels=[], components=components or ["Web"], fix_versions=["2026.10"], comments=comments or [],
        custom_fields={}, url=f"https://jira.example/browse/{key}",
    )


@dataclass
class FakeResult:
    output: str
    provider: str = "fake"
    model: str = "fake-1"


@dataclass
class FakeAgent:
    """Answers each stage from the instruction text; records every call."""
    name: str = "Fake Writer"
    calls: List[Dict] = field(default_factory=list)

    async def run(self, instructions: str, input_text: str = "", max_tokens=None, temperature=None) -> FakeResult:
        self.calls.append({"instructions": instructions[:60], "input": input_text})
        if "deciding what belongs in the release notes" in instructions or "reviewing Jira issues" in instructions:
            issues = json.loads(input_text)
            out = {"issues": []}
            for issue in issues:
                relevant = "refactor" not in issue["summary"].lower()
                notes = [{"title": f"Note for {issue['key']}", "summary": f"Summary of {issue['summary']}", "category": "Improvements"}] if relevant else []
                out["issues"].append({"key": issue["key"], "relevant": relevant, "reason": "fake", "notes": notes})
            return FakeResult(json.dumps(out))
        if "final list of notes" in instructions:
            candidates = json.loads(input_text)
            return FakeResult(json.dumps({"items": [
                {"title": c["title"], "summary": c["summary"], "category": c["category"], "issue_keys": c["issue_keys"]}
                for c in candidates
            ]}))
        if "organizing release notes" in instructions:
            items = json.loads(input_text)
            return FakeResult(json.dumps({"groups": [{"name": "Improvements", "notes": [i["n"] for i in items]}]}))
        # write / rewrite
        record = json.loads(input_text.split("\n\n## ", 1)[0])
        marker = "rewritten" if "what_changed_in_jira" in record else "written"
        return FakeResult(f'<div><p><b>{record["title"]}</b></p><p>{marker}: {record["summary"]}</p></div>')


# ── Fixtures ─────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    session = get_session_factory()()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def seeded_job(db):
    """An organization, user, agent, instruction set and job that are deleted afterwards."""
    from app.models.database import Agent, InstructionSet, Job, JobStatus, JobTrigger, Organization, User

    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Pipeline test {suffix}", slug=f"pipeline-test-{suffix}")
    db.add(org)
    db.flush()
    user = User(email=f"pipeline-{suffix}@example.test", password_hash="x", is_active=True)
    db.add(user)
    db.flush()
    agent = Agent(organization_id=org.id, user_id=user.id, name="Fake Writer", is_active=True)
    db.add(agent)
    db.flush()
    instruction_set = InstructionSet(
        user_id=user.id, organization_id=org.id, name="Test set", jql_query="project = T",
        writer_agent_id=agent.id, product_name="Testo", chunking_strategy="single",
    )
    db.add(instruction_set)
    db.flush()
    job = Job(
        user_id=user.id, organization_id=org.id, instruction_set_id=instruction_set.id, jql_query="project = T",
        status=JobStatus.PENDING, triggered_by=JobTrigger.MANUAL, output_filename="test-notes.dita", title="Testo 2026.10",
    )
    db.add(job)
    db.commit()
    yield job
    db.rollback()
    db.delete(db.get(Job, job.id))
    db.delete(db.get(InstructionSet, instruction_set.id))
    db.delete(db.get(Agent, agent.id))
    db.delete(db.get(User, user.id))
    db.delete(db.get(Organization, org.id))
    db.commit()


def _run(db, job_id, tickets: List[JiraTicket], agent: FakeAgent):
    from app.services import release_notes_pipeline as module

    pipeline = module.ReleaseNotesPipeline(db, job_id)

    async def fake_fetch(job):
        return tickets

    def fake_resolve(job):
        pipeline.writer = agent
        pipeline.analyst = agent

    pipeline._fetch_issues = fake_fetch
    pipeline._resolve_agents = fake_resolve
    asyncio.run(pipeline.run())
    db.expire_all()
    return db.get(module.Job, job_id)


# ── Tests ────────────────────────────────────────────────────────────────────────────

def test_first_run_then_rerun_with_changes(db, seeded_job):
    from app.models.database import HistoryEvent, IssueRelevance, ItemStatus

    agent = FakeAgent()
    first = [
        _ticket("T-1", "Faster search", "Search got faster"),
        _ticket("T-2", "Export to PDF", "You can export"),
        _ticket("T-3", "Refactor the build", "internal"),
    ]
    job = _run(db, seeded_job.id, first, agent)

    assert job.status.value == "completed", job.error_message
    assert job.stage == "done"
    by_key = {i.issue_key: i for i in job.issues}
    assert by_key["T-3"].relevance == IssueRelevance.NOT_RELEVANT
    assert by_key["T-1"].relevance == IssueRelevance.RELEVANT
    titles = sorted(i.title for i in job.items)
    assert titles == ["Note for T-1", "Note for T-2"]
    for item in job.items:
        assert item.group_name == "Improvements"
        assert "written:" in item.dita_content
        assert item.dita_content.startswith(f'<div id="{item.fragment_id}"')
        assert [h.event_type for h in item.history] == [HistoryEvent.CREATED]
    assert len(job.topics) == 1
    topic = job.topics[0]
    assert topic.title == "Testo 2026.10"
    assert all(item.fragment_id in topic.dita_content for item in job.items)
    assert any(a.artifact_type == "dita" for a in job.artifacts)

    # A person edits the T-2 note; the rerun must not overwrite it.
    t2_item = next(i for i in job.items if "T-2" in [l.issue.issue_key for l in i.issue_links])
    t2_item.user_edited = True
    t2_item.dita_content = f'<div id="{t2_item.fragment_id}" outputclass="release-note"><p><b>Hand written</b></p></div>'
    db.commit()
    t1_item = next(i for i in job.items if i is not t2_item)
    t1_content_before = t1_item.dita_content

    # Rerun: T-1 changed (status + comment), T-2 changed, T-3 gone, T-4 new.
    second = [
        _ticket("T-1", "Faster search", "Search got faster", status="Released", comments=["Shipped!"]),
        _ticket("T-2", "Export to PDF and DOCX", "You can export"),
        _ticket("T-4", "Dark mode", "Dark mode is here"),
    ]
    agent.calls.clear()
    job = _run(db, seeded_job.id, second, agent)

    assert job.status.value == "completed", job.error_message
    assert job.run_count == 2
    items = {i.title: i for i in job.items}
    assert set(items) == {"Note for T-1", "Note for T-2", "Note for T-4"}

    # T-1: untouched note is rewritten, with the change and the previous content on record.
    t1 = items["Note for T-1"]
    assert t1.dita_content != t1_content_before and "rewritten:" in t1.dita_content
    events = [h.event_type for h in t1.history]
    assert HistoryEvent.JIRA_CHANGED in events and HistoryEvent.REGENERATED in events
    change = next(h for h in t1.history if h.event_type == HistoryEvent.JIRA_CHANGED)
    assert "Status: Done → Released" in change.summary and "1 new comment" in change.summary
    assert change.details["changes"]["comments"]["added"] == ["Shipped!"]
    regenerated = next(h for h in t1.history if h.event_type == HistoryEvent.REGENERATED)
    assert regenerated.details["previous_dita"] == t1_content_before
    assert not t1.needs_attention

    # T-2: the person's edit is kept and the note is flagged instead.
    t2 = items["Note for T-2"]
    assert "Hand written" in t2.dita_content
    assert t2.needs_attention and "T-2 changed in Jira" in t2.attention_reason
    assert HistoryEvent.FLAGGED in [h.event_type for h in t2.history]

    # T-3 was never a note; T-4 is new and joins the existing group.
    t4 = items["Note for T-4"]
    assert t4.group_name == "Improvements" and "written:" in t4.dita_content
    assert [h.event_type for h in t4.history] == [HistoryEvent.CREATED]

    # The snapshot keeps T-3 out of the query without deleting it.
    by_key = {i.issue_key: i for i in job.issues}
    assert set(by_key) == {"T-1", "T-2", "T-3", "T-4"}
    assert by_key["T-3"].in_query is False and by_key["T-4"].in_query is True

    # Only the new and the rewritten notes went to the writer.
    write_calls = [c for c in agent.calls if c["instructions"].startswith("Write the release note") or c["instructions"].startswith("Your previous")]
    assert len(write_calls) == 2

    # Topics were re-assembled with every included note.
    assert len(job.topics) == 1
    for item in job.items:
        if item.status != ItemStatus.REJECTED:
            assert item.fragment_id in job.topics[0].dita_content


def test_removed_issue_flags_its_note(db, seeded_job):
    from app.models.database import HistoryEvent

    agent = FakeAgent()
    job = _run(db, seeded_job.id, [_ticket("T-9", "Only change", "x")], agent)
    assert job.status.value == "completed", job.error_message
    assert len(job.items) == 1

    job = _run(db, seeded_job.id, [], agent)
    assert job.status.value == "completed", job.error_message
    item = job.items[0]
    assert item.needs_attention and "no longer matches" in item.attention_reason
    assert HistoryEvent.ISSUE_REMOVED in [h.event_type for h in item.history]
    # The note still has its source issue.
    assert [l.issue.issue_key for l in item.issue_links] == ["T-9"]


def test_rerun_evaluates_issues_a_failed_run_left_pending(db, seeded_job):
    """A run that snapshots issues and then fails must not leave them unjudged forever."""
    from app.models.database import IssueRelevance

    class ExplodingAgent(FakeAgent):
        async def run(self, instructions, input_text="", max_tokens=None, temperature=None):
            raise RuntimeError("Anthropic returned HTTP 400: boom")

    tickets = [_ticket("T-5", "Keyboard shortcuts", "Shortcuts for everything")]
    job = _run(db, seeded_job.id, tickets, ExplodingAgent())
    assert job.status.value == "failed"
    assert [i.relevance for i in job.issues] == [IssueRelevance.PENDING]
    assert job.items == []

    job = _run(db, seeded_job.id, tickets, FakeAgent())
    assert job.status.value == "completed", job.error_message
    assert [i.relevance for i in job.issues] == [IssueRelevance.RELEVANT]
    assert [i.title for i in job.items] == ["Note for T-5"]
