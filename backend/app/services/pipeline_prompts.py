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
        # The issue's page in Jira, so a note that is meant to link its issue can: the
        # writer has no other way to know which Jira site the keys belong to.
        "url": issue.url,
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

def organize_instructions(output_guidance: Optional[str], existing_groups: Sequence[str]) -> str:
    """Group and order the notes, following the instruction set's output guidance.

    The guidance describes the whole output — topic structure and note formatting as well
    as grouping — because it is one field that several agents read. This stage takes from
    it only which groups exist, what they are called and in what order things appear.
    """
    guidance = (output_guidance or "").strip()
    if guidance:
        guidance_block = (
            "\n\n## How these release notes are organized\n\n"
            "The guidance below describes the whole output. From it, take which groups the notes "
            "fall into, what each group is called, the order of the groups, and the order of notes "
            "within a group; ignore what it says about markup and wording, which other stages "
            "apply. A group's name is printed as its heading, so name each group exactly as the "
            "guidance says its heading reads. When a heading includes a version, take it from the "
            "notes' fix_versions in the input, in the format the guidance gives; never invent one."
            f"\n\n{guidance}"
        )
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
        # The Jira versions the note shipped in: what a group heading like
        # "Heretto Portal v6 26.10.22" is built from. Without them a version is a guess.
        fix_versions = sorted({v for i in item.issues for v in (i.fix_versions or [])})
        records.append({
            "n": index,
            "title": item.title,
            "summary": item.summary,
            "category": item.group_name,
            "issue_types": issue_types,
            "components": components,
            "fix_versions": fix_versions,
            "issue_keys": [i.issue_key for i in item.issues],
        })
    return json.dumps(records, indent=1, ensure_ascii=False)


# ── Stage 5: write ───────────────────────────────────────────────────────────────────

FRAGMENT_FORMAT = """## Output format

Return the body of one release note and nothing else: DITA 1.3 elements, no wrapper around
them. No XML declaration, no DOCTYPE, no <topic>, no <section>, no <title>, no <div>, no
markdown, no commentary before or after. The element the note sits in is added when the
notes are assembled into topics, and it differs between instruction sets — so returning one
yourself gets it thrown away at best.

<p><b>Headline for the change</b></p>
<p>What changed, written for the person it affects, and what they can now do or should do.</p>

You may use <p>, <ul>/<ol> with <li>, <b>, <i>, <codeph> (for inline code, commands and
setting names), <codeblock> (for code blocks), <uicontrol> (for UI labels such as buttons and
menu items), <filepath> (for file and directory paths), <note type="note|important|warning|tip">,
<dl> with <dlentry><dt/><dd/></dlentry>, <simpletable>, and
<xref href="https://…" scope="external" format="html">. Do NOT use <title>, <section>,
headings, <div>, or Markdown. Escape &, < and > in text (&amp; &lt; &gt;). Mention Jira issue
keys or link issues only if your guidance asks for them; to link one, use the issue's "url"
from the input as the <xref> href, never a URL you construct."""


def house_style(guidance: Optional[str]) -> str:
    """The instruction set's output guidance, as the writer sees it.

    The same text goes to organize (group names and order) and, in "Describe it" mode, to
    the template agent (topic structure). The writer gets it because it also says how a
    note is formatted — the label it opens with, which elements to use, whether it links
    its issue — and that is the writer's to do. Tone and voice are not in it: those come
    from the writer agent's own configuration.

    Scoped on the way in: a single note is all this agent can affect. Rules about the topic
    around it are carried out by assembly, and telling the writer to produce them makes it
    emit fragments that fail validation.
    """
    guidance = (guidance or "").strip()
    if not guidance:
        return ""
    return f"""

## Output guidance

These rules come from the instruction set and are **binding**. Follow everything in them
that governs this one release note: how it opens, what tense and voice it uses, what
wording is required, which elements to use.

Ignore anything that describes the document *around* this note — the topic title,
<shortdesc>, sections, how notes are grouped or ordered, headings per product. Those are
applied when the notes are assembled into topics, and emitting them here produces an
invalid fragment. Return the note's content with no wrapper, as described below, whatever
the rules say about the wider structure.

{guidance}"""


def write_instructions(product: str, guidance: Optional[str] = None) -> str:
    return f"""Write the release note for {product} described in the input, following your style
guidance. Write for the reader who will use the change: say what is new or different and what
it means for them, concretely. Do not pad with phrases like "we are excited"; do not describe
internal implementation. Use the Jira issues for facts only — do not copy ticket prose
verbatim and do not include anything a customer should not see (internal names, customer
names, credentials).{house_style(guidance)}

{FRAGMENT_FORMAT}"""


def rewrite_instructions(product: str, errors: Sequence[str], guidance: Optional[str] = None) -> str:
    listed = "\n".join(f"- {e}" for e in errors)
    # The output guidance rides along: a retry that drops it fixes the DITA and loses the
    # wording the first attempt got right.
    return f"""Your previous fragment for this release note was not valid DITA. Fix these problems and
return the corrected fragment only:

{listed}{house_style(guidance)}

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


def topic_structure_instructions(guidance: str) -> str:
    """Ask an agent for a topic template that matches a description of the structure.

    It returns a template, not a finished topic: the template is kept on the release and
    reused by every later assembly, so the shape stays put while notes are edited, and no
    model call sits inside a request.
    """
    return f"""You are turning a description of a release-notes topic structure into a DITA
topic template. Return the template and nothing else — no commentary, no code fences.

## The output wanted

The description covers the whole output. Take from it only the structure of the topic: what
surrounds the notes, what repeats per group, and what fixed content appears where. What it
says about how each note is worded or marked up, and about which groups exist and in what
order, is applied by other stages — leave it out of the template.

{guidance.strip()}

## What a template is

A valid DITA 1.3 <topic>. It is filled in when the release notes are assembled, using two
markers and two tokens:

- Put outputclass="rn-notes" on the element the notes go inside. Its tag decides what each
  note becomes: a <ul> or <ol> makes every note an <li>; anything else makes it a <div>.
- Put outputclass="rn-group" on the element that should repeat once per group of notes. The
  rn-notes element must be inside it. Leave rn-group out only if the structure does not
  group notes at all.
- {{title}} anywhere in the text is replaced by the release's title.
- {{group}} inside the repeating block is replaced by that group's name.
- Content that belongs to only some groups — an introduction that comes before one
  product's heading, say — goes inside the repeating block with rn-for-group="…" naming
  the group. It is kept only for groups whose name contains that text (ignoring case;
  separate alternatives with |) and dropped for every other group. Group names carry a
  version, so name the product ("Cloud Publishing"), not the version. Never put
  rn-for-group on the rn-notes element or anything containing it.

Everything else in the template is emitted as written, so fixed paragraphs, <ph
conkeyref="..."/> references and a populated <shortdesc> all belong in it.

## Example

<topic id="placeholder">
  <title>{{title}}</title>
  <shortdesc/>
  <body>
    <section outputclass="rn-group">
      <p rn-for-group="Cloud Publishing">Cloud Publishing ships separately from the CCMS.</p>
      <p><b>{{group}}</b></p>
      <ul outputclass="rn-notes"/>
    </section>
  </body>
</topic>

Return one <topic> that implements the structure described above."""
