"""The instructions each pipeline stage gives its agent, and how issues are shown to it.

Agents carry their own persona, context files, style guides and feedback memory (hop-core
``AgentDefinition``); these are the per-stage task instructions layered on top. Every
structured stage asks for JSON and nothing else; the writer asks for one DITA fragment.
"""

from __future__ import annotations

import json
from typing import Iterable, List, Optional, Sequence

from app.models.database import JobJiraIssue, ReleaseNoteItem


def _clip(text: Optional[str], limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " […]"


def issue_record(issue: JobJiraIssue, description_limit: int = 1800, comment_limit: int = 400, max_comments: int = 6) -> dict:
    """An issue as the agent sees it: everything that can bear on a release note."""
    comments = [_clip(c, comment_limit) for c in (issue.comments or [])[-max_comments:] if c and c.strip()]
    return {
        "key": issue.issue_key,
        "type": issue.issue_type,
        "status": issue.status,
        "priority": issue.priority,
        "summary": issue.summary,
        "description": _clip(issue.description, description_limit),
        "labels": list(issue.labels or []),
        "components": list(issue.components or []),
        "fix_versions": list(issue.fix_versions or []),
        "comments": comments,
    }


def issues_json(issues: Iterable[JobJiraIssue]) -> str:
    return json.dumps([issue_record(i) for i in issues], indent=1, ensure_ascii=False)


# ── Stage 2: evaluate ────────────────────────────────────────────────────────────────

def evaluate_instructions(product: str, relevance_guidance: Optional[str]) -> str:
    guidance = (relevance_guidance or "").strip()
    guidance_block = f"\n\n## What counts as relevant for this product\n\n{guidance}" if guidance else ""
    return f"""You are reviewing Jira issues to decide what belongs in the release notes for {product}.

For every issue in the input, decide whether it contains a change that end users (customers,
administrators, integrators) need to know about. Internal refactors, test-only work, build and
tooling changes, duplicate or abandoned tickets, and work that does not change what a user can
see or do are NOT relevant. A single issue can contain several user-facing changes — list each
one separately. Several notes may come from one issue; never invent changes the issue does
not describe.{guidance_block}

## Output

Return JSON only, no prose, in exactly this shape:

{{
  "issues": [
    {{
      "key": "PROJ-123",
      "relevant": true,
      "reason": "one sentence explaining the decision",
      "notes": [
        {{
          "title": "short headline for the change, in the product's voice",
          "summary": "two or three plain-language sentences describing what changed and why a user cares",
          "category": "a short category such as New feature, Improvement, Fix, Deprecation, Security, Known issue"
        }}
      ]
    }}
  ]
}}

An issue that is not relevant has "relevant": false and an empty "notes" list. Every input
issue must appear exactly once in the output."""


# ── Stage 3: consolidate ─────────────────────────────────────────────────────────────

CONSOLIDATE_INSTRUCTIONS = """You are turning candidate release notes into the final list of notes.

The input is a list of candidates, each with the Jira issue keys it came from. Merge
candidates that describe the same user-facing change (for example, a story and the bug fixed
while delivering it, or the same feature mentioned by two issues) into one note that keeps
every contributing issue key. Keep distinct changes separate. Do not drop a candidate unless
it duplicates another; do not add changes that no candidate describes. Keep titles short and
summaries concrete.

## Output

Return JSON only, in exactly this shape:

{
  "items": [
    {
      "title": "short headline",
      "summary": "two or three plain-language sentences",
      "category": "the category",
      "issue_keys": ["PROJ-123", "PROJ-130"]
    }
  ]
}
"""


def candidates_json(candidates: Sequence[dict]) -> str:
    return json.dumps(
        [
            {
                "n": index,
                "title": c.get("title"),
                "summary": c.get("summary"),
                "category": c.get("category"),
                "issue_keys": c.get("issue_keys", []),
            }
            for index, c in enumerate(candidates, start=1)
        ],
        indent=1,
        ensure_ascii=False,
    )


# ── Stage 4: organize ────────────────────────────────────────────────────────────────

def organize_instructions(organization_guidance: Optional[str], existing_groups: Sequence[str]) -> str:
    guidance = (organization_guidance or "").strip()
    if guidance:
        guidance_block = f"\n\n## How these release notes are organized\n\n{guidance}"
    else:
        guidance_block = (
            "\n\n## How these release notes are organized\n\n"
            "Group by the kind of change, in this order where present: New features, Improvements, "
            "Fixes, Security, Deprecations and removals, Known issues. Within a group put the changes "
            "that affect the most users first."
        )
    existing_block = ""
    if existing_groups:
        listed = "\n".join(f"- {g}" for g in existing_groups)
        existing_block = (
            "\n\n## Existing groups\n\nThese groups already exist and must keep their names and order. "
            "Place every new note into one of them when it fits; add a new group only when none fits.\n\n"
            + listed
        )
    return f"""You are organizing release notes into groups and putting them in order.{guidance_block}{existing_block}

## Output

Return JSON only, in exactly this shape. Groups are listed in the order they should appear and
each group lists its notes (by their "n" number) in reading order. Every input note must appear
exactly once.

{{
  "groups": [
    {{ "name": "New features", "notes": [3, 1] }},
    {{ "name": "Fixes", "notes": [2] }}
  ]
}}"""


def organize_input(items: Sequence[ReleaseNoteItem]) -> str:
    records = []
    for index, item in enumerate(items, start=1):
        issue_types = sorted({i.issue_type for i in item.issues if i.issue_type})
        components = sorted({c for i in item.issues for c in (i.components or [])})
        records.append({
            "n": index,
            "title": item.title,
            "summary": item.summary,
            "category": item.group_name,
            "issue_types": issue_types,
            "components": components,
            "issue_keys": [i.issue_key for i in item.issues],
        })
    return json.dumps(records, indent=1, ensure_ascii=False)


# ── Stage 5: write ───────────────────────────────────────────────────────────────────

FRAGMENT_FORMAT = """## Output format

Return exactly one DITA 1.3 fragment and nothing else: a single <div> element. No XML
declaration, no DOCTYPE, no <topic>, no <section>, no <title>, no markdown, no commentary
before or after it.

<div outputclass="release-note">
  <p><b>Headline for the change</b></p>
  <p>What changed, written for the person it affects, and what they can now do or should do.</p>
</div>

Inside the <div> you may use <p>, <ul>/<ol> with <li>, <b>, <i>, <tt> (for code, names of
settings, paths and UI labels), <pre> (for code blocks), <note type="note|important|warning|tip">,
<dl> with <dlentry><dt/><dd/></dlentry>, <simpletable>, and
<xref href="https://…" scope="external" format="html">. Do NOT use <codeph>, <codeblock>,
<uicontrol>, <filepath>, <title>, <section>, headings, nested <div>, or Markdown. Escape &, <
and > in text (&amp; &lt; &gt;). Mention Jira issue keys only if your style guidance asks for them."""


def write_instructions(product: str) -> str:
    return f"""Write the release note for {product} described in the input, following your style
guidance. Write for the reader who will use the change: say what is new or different and what
it means for them, concretely. Do not pad with phrases like "we are excited"; do not describe
internal implementation. Use the Jira issues for facts only — do not copy ticket prose
verbatim and do not include anything a customer should not see (internal names, customer
names, credentials).

{FRAGMENT_FORMAT}"""


def rewrite_instructions(product: str, errors: Sequence[str]) -> str:
    listed = "\n".join(f"- {e}" for e in errors)
    return f"""Your previous fragment for this release note was not valid DITA. Fix these problems and
return the corrected fragment only:

{listed}

{FRAGMENT_FORMAT}"""


def write_input(item: ReleaseNoteItem, previous_fragment: Optional[str] = None) -> str:
    record = {
        "title": item.title,
        "summary": item.summary,
        "group": item.group_name,
        "issues": [issue_record(i) for i in item.issues],
    }
    text = json.dumps(record, indent=1, ensure_ascii=False)
    if previous_fragment:
        text += f"\n\n## Previous fragment\n\n{previous_fragment}"
    return text


def regenerate_input(item: ReleaseNoteItem, change_summary: str) -> str:
    record = {
        "title": item.title,
        "summary": item.summary,
        "group": item.group_name,
        "what_changed_in_jira": change_summary,
        "issues": [issue_record(i) for i in item.issues],
    }
    return (
        json.dumps(record, indent=1, ensure_ascii=False)
        + "\n\n## Current fragment (rewrite it to reflect the Jira changes; keep what is still true)\n\n"
        + (item.dita_content or "")
    )
