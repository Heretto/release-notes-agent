"""Snapshotting Jira issues on a job, and telling what changed since the last run.

Each issue the query returns is stored once per job (``JobJiraIssue``) with a content hash over
the fields a release note can depend on. A rerun compares the fresh tickets to the snapshot and
sorts them into new / changed / unchanged / removed, with a field-level diff for the changed
ones so the note's history can say exactly what moved.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.database import Job, JobJiraIssue
from app.models.schemas import JiraTicket

# Fields that feed a release note. Custom fields are deliberately excluded: rank, sprint and
# similar bookkeeping fields churn constantly and never change what a note should say.
HASH_FIELDS: Tuple[str, ...] = (
    "summary", "description", "issue_type", "status", "priority",
    "labels", "components", "fix_versions", "comments",
)

# What the UI shows for a changed field, so the diff reads like a sentence.
FIELD_LABELS = {
    "summary": "Summary",
    "description": "Description",
    "issue_type": "Issue type",
    "status": "Status",
    "priority": "Priority",
    "labels": "Labels",
    "components": "Components",
    "fix_versions": "Fix versions",
    "comments": "Comments",
}


def ticket_fields(ticket: JiraTicket) -> Dict[str, Any]:
    """The snapshot column values for a ticket."""
    return {
        "issue_key": ticket.key,
        "url": ticket.url,
        "summary": ticket.summary or "",
        "description": ticket.description,
        "issue_type": ticket.issue_type,
        "status": ticket.status,
        "priority": ticket.priority,
        "labels": list(ticket.labels or []),
        "components": list(ticket.components or []),
        "fix_versions": list(ticket.fix_versions or []),
        "comments": list(ticket.comments or []),
        "assignee": ticket.assignee,
        "reporter": ticket.reporter,
        "jira_created": ticket.created,
        "jira_updated": ticket.updated,
    }


def content_hash(ticket: JiraTicket) -> str:
    """A stable hash over HASH_FIELDS; identical content hashes identically across runs."""
    values = ticket_fields(ticket)
    payload = {name: values[name] for name in HASH_FIELDS}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _summarize(value: Any, limit: int = 300) -> Any:
    """Keep diffs readable: long text is clipped, lists pass through."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def diff_fields(issue: JobJiraIssue, ticket: JiraTicket) -> Dict[str, Dict[str, Any]]:
    """Field-by-field changes between the stored snapshot and the fresh ticket."""
    fresh = ticket_fields(ticket)
    changes: Dict[str, Dict[str, Any]] = {}
    for name in HASH_FIELDS:
        before = getattr(issue, name)
        after = fresh[name]
        if name == "comments":
            # Only new comments matter; a diff of the whole list reads as noise.
            old_comments = list(before or [])
            new_comments = [c for c in (after or []) if c not in old_comments]
            if new_comments or len(after or []) != len(old_comments):
                changes[name] = {
                    "label": FIELD_LABELS[name],
                    "added": [_summarize(c) for c in new_comments],
                    "count_before": len(old_comments),
                    "count_after": len(after or []),
                }
            continue
        if (before or None) != (after or None) and not (before in ([], "") and after in ([], "", None)):
            changes[name] = {
                "label": FIELD_LABELS[name],
                "from": _summarize(before),
                "to": _summarize(after),
            }
    return changes


def describe_diff(changes: Dict[str, Dict[str, Any]]) -> str:
    """One line for a history entry: 'Status: In Progress → Done; Description changed'."""
    parts: List[str] = []
    for name, change in changes.items():
        label = change.get("label", name)
        if name == "comments":
            added = len(change.get("added") or [])
            parts.append(f"{added} new comment{'s' if added != 1 else ''}" if added else "comments changed")
        elif name in ("description",):
            parts.append(f"{label} changed")
        elif isinstance(change.get("from"), list) or isinstance(change.get("to"), list):
            parts.append(f"{label} changed")
        else:
            parts.append(f"{label}: {change.get('from') or '—'} → {change.get('to') or '—'}")
    return "; ".join(parts)


@dataclass
class SnapshotResult:
    """How the fresh query result relates to the stored snapshot."""
    new: List[JobJiraIssue] = field(default_factory=list)
    changed: List[Tuple[JobJiraIssue, Dict[str, Dict[str, Any]]]] = field(default_factory=list)
    unchanged: List[JobJiraIssue] = field(default_factory=list)
    removed: List[JobJiraIssue] = field(default_factory=list)
    # Issues that had dropped out of the query on an earlier run and are back.
    returned: List[JobJiraIssue] = field(default_factory=list)

    @property
    def seen(self) -> List[JobJiraIssue]:
        return self.new + [issue for issue, _ in self.changed] + self.unchanged


def sync_snapshot(db: Session, job: Job, tickets: List[JiraTicket]) -> SnapshotResult:
    """Bring the job's issue snapshot in line with ``tickets`` and report what changed.

    Issues no longer returned are kept with ``in_query = False`` so the notes written from
    them keep their source; nothing is deleted. The caller commits.
    """
    existing: Dict[str, JobJiraIssue] = {issue.issue_key: issue for issue in job.issues}
    now = datetime.now(timezone.utc)
    result = SnapshotResult()
    seen_keys = set()

    for ticket in tickets:
        if not ticket.key or ticket.key in seen_keys:
            continue
        seen_keys.add(ticket.key)
        fresh_hash = content_hash(ticket)
        issue = existing.get(ticket.key)
        if issue is None:
            issue = JobJiraIssue(job_id=job.id, content_hash=fresh_hash, **ticket_fields(ticket))
            issue.first_seen_at = now
            issue.last_seen_at = now
            db.add(issue)
            job.issues.append(issue)
            result.new.append(issue)
            continue

        was_removed = not issue.in_query
        issue.in_query = True
        issue.last_seen_at = now
        if issue.content_hash == fresh_hash:
            # Keep the bookkeeping fields fresh even when nothing a note depends on moved.
            issue.jira_updated = ticket.updated or issue.jira_updated
            issue.assignee = ticket.assignee
            issue.url = ticket.url or issue.url
            (result.returned if was_removed else result.unchanged).append(issue)
            continue

        changes = diff_fields(issue, ticket)
        for name, value in ticket_fields(ticket).items():
            setattr(issue, name, value)
        issue.content_hash = fresh_hash
        issue.changed_at = now
        result.changed.append((issue, changes))

    for key, issue in existing.items():
        if key not in seen_keys and issue.in_query:
            issue.in_query = False
            result.removed.append(issue)

    return result
