"""The workspace chat: a person talks to the writer agent, the agent edits through tools.

Every change the agent makes goes through the same functions the API uses for a person's own
edits, so it is validated the same way and lands in the note's history with ``actor="agent"``.
The reply the person sees is the agent's own text; the tool calls it made are returned with it
so the UI can show what changed.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy.orm import Session

from hop_core.agents.fetcher import fetch_url
from hop_core.agents.providers import READ_URL_TOOL
from hop_core.ai import ChatMessage, GenerationRequest, ToolSpec
from hop_core.dita import DitaValidator

from app.models.database import (
    ChunkingStrategy, HistoryEvent, ItemStatus, Job, ReleaseNoteChatMessage, ReleaseNoteItem,
    ReleaseNoteItemIssue,
)
from app.models.schemas import ChatSendResponse
from app.services.agents import AgentUnavailable, resolve_agent
from app.services.pipeline_prompts import FRAGMENT_FORMAT, issue_record
from app.services.topic_assembler import FragmentError, coerce_fragment
from app.services.workspace_service import (
    assemble_job_topics, chat_message_to_response, group_order, move_item, product_name,
    record_history, release_title, set_item_content,
)

logger = logging.getLogger(__name__)

HISTORY_TURNS = 20


class ChatUnavailable(Exception):
    """The chat cannot run; the message is safe to show a person."""


def _tool(name: str, description: str, properties: Dict[str, Any], required: List[str]) -> ToolSpec:
    return ToolSpec(
        name=name, description=description,
        parameters={"type": "object", "properties": properties, "required": required},
    )


NOTE_ID = {"type": "string", "description": "The note's id as listed in the workspace (e.g. rn-1a2b3c4d)."}

TOOLS: List[ToolSpec] = [
    _tool("read_note", "Read a note in full: its DITA fragment, summary, status, and the Jira issues behind it.",
          {"note_id": NOTE_ID}, ["note_id"]),
    _tool("read_issue", "Read a Jira issue from the job's snapshot: summary, description, status, comments.",
          {"issue_key": {"type": "string", "description": "The Jira key, e.g. PROJ-123."}}, ["issue_key"]),
    _tool("update_note",
          "Change a note's headline, summary and/or DITA content. Send the COMPLETE fragment when "
          "changing content — one <div outputclass=\"release-note\"> element. Invalid DITA is "
          "rejected with the errors; fix them and call again.",
          {"note_id": NOTE_ID,
           "title": {"type": "string", "description": "New headline (optional)."},
           "summary": {"type": "string", "description": "New plain-language summary (optional)."},
           "dita_content": {"type": "string", "description": "The complete replacement fragment (optional)."}},
          ["note_id"]),
    _tool("set_note_status", "Set a note's review status. 'rejected' removes it from the output.",
          {"note_id": NOTE_ID,
           "status": {"type": "string", "enum": list(ItemStatus.ALL)}},
          ["note_id", "status"]),
    _tool("move_note", "Move a note into a group and/or to a 1-based position inside its group.",
          {"note_id": NOTE_ID,
           "group_name": {"type": "string", "description": "Target group; created if new (optional)."},
           "position": {"type": "integer", "description": "1-based position inside the group (optional)."}},
          ["note_id"]),
    _tool("rename_group", "Rename a group; every note in it moves with it.",
          {"old_name": {"type": "string"}, "new_name": {"type": "string"}}, ["old_name", "new_name"]),
    _tool("create_note", "Add a new release note. Link it to the Jira issues it comes from when you can.",
          {"title": {"type": "string"},
           "summary": {"type": "string"},
           "dita_content": {"type": "string", "description": "The complete fragment (optional; the summary is used if omitted)."},
           "group_name": {"type": "string"},
           "issue_keys": {"type": "array", "items": {"type": "string"}}},
          ["title", "summary"]),
    _tool("reorganize_topics",
          "Re-split the notes into DITA topics: 'single' (one topic), 'by_group' (one per group), "
          "'by_component' (one per Jira component).",
          {"strategy": {"type": "string", "enum": list(ChunkingStrategy.ALL)}}, ["strategy"]),
]


def _short(value: Any, limit: int = 300) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


class WorkspaceChat:
    def __init__(self, db: Session, job: Job, user_id: Optional[UUID], validator: Optional[DitaValidator] = None):
        self.db = db
        self.job = job
        self.user_id = user_id
        self.validator = validator or DitaValidator()
        self.changed_items: Set[UUID] = set()
        self.topics_changed = False
        self.actions: List[Dict[str, Any]] = []
        self._requested_strategy: Optional[str] = None

    # ── Public ───────────────────────────────────────────────────────────────────────

    async def send(self, message: str, selected_item_id: Optional[UUID] = None) -> ChatSendResponse:
        instruction_set = self.job.instruction_set
        if instruction_set is None:
            raise ChatUnavailable("The job's instruction set no longer exists.")
        try:
            agent = resolve_agent(self.db, instruction_set.writer_agent, self.job.organization_id, "writer")
        except AgentUnavailable as exc:
            raise ChatUnavailable(str(exc)) from exc

        definition = await agent.runner.prepare(agent.definition)
        selected = self._find_item(str(selected_item_id)) if selected_item_id else None
        system_prompt = definition.build_system_prompt() + "\n\n" + self._workspace_context(selected)

        history = self._history()
        turns = history + [ChatMessage(role="user", content=message)]
        tools = list(TOOLS)
        if definition.permitted_urls:
            tools.append(READ_URL_TOOL)

        request = GenerationRequest(
            system_prompt=system_prompt,
            user_prompt=message,
            messages=turns,
            max_tokens=4096,
            temperature=None,  # several Anthropic models reject it; provider defaults are fine
            tools=tools,
        )
        executor = self._executor(definition.permitted_urls)
        try:
            response = await agent.service.generate_with_tools(request, executor)
        except Exception as exc:
            logger.error("Workspace chat failed for job %s: %s", self.job.id, exc, exc_info=True)
            self.db.rollback()
            raise ChatUnavailable(f"The agent could not answer: {exc}") from exc

        reply = (response.content or "").strip()
        if not reply:
            reply = self._fallback_reply()

        user_message = ReleaseNoteChatMessage(job_id=self.job.id, user_id=self.user_id, role="user", content=message)
        assistant_message = ReleaseNoteChatMessage(
            job_id=self.job.id, user_id=None, role="assistant", content=reply, actions=self.actions or None,
        )
        self.db.add_all([user_message, assistant_message])

        if self.changed_items or self.topics_changed:
            try:
                assemble_job_topics(self.db, self.job, self._requested_strategy, self.validator)
            except FragmentError as exc:
                logger.error("Reassembly after chat failed for job %s: %s", self.job.id, exc.errors)
        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_message)
        return ChatSendResponse(
            user_message=chat_message_to_response(user_message),
            assistant_message=chat_message_to_response(assistant_message),
            changed_item_ids=sorted(self.changed_items, key=str),
            topics_changed=bool(self.changed_items or self.topics_changed),
        )

    # ── Context ──────────────────────────────────────────────────────────────────────

    def _history(self) -> List[ChatMessage]:
        rows = sorted(self.job.chat_messages, key=lambda m: m.created_at or 0)[-HISTORY_TURNS:]
        turns = [ChatMessage(role=m.role, content=m.content) for m in rows if m.role in ("user", "assistant")]
        while turns and turns[0].role != "user":
            turns.pop(0)
        return turns

    def _workspace_context(self, selected: Optional[ReleaseNoteItem]) -> str:
        job = self.job
        groups = group_order(job)
        lines = []
        for item in sorted(job.items, key=lambda i: i.position):
            keys = ", ".join(link.issue.issue_key for link in item.issue_links) or "no issues"
            flag = " ⚠ needs attention" if item.needs_attention else ""
            lines.append(
                f"- {item.fragment_id} | {item.group_name or '(no group)'} | {item.status}{flag} | "
                f"{item.title} — {_short(item.summary, 160)} [{keys}]"
            )
        selected_block = ""
        if selected is not None:
            selected_block = (
                f"\n\n## The note the person is looking at: {selected.fragment_id}\n\n"
                f"Title: {selected.title}\nSummary: {selected.summary}\n\n{selected.dita_content}"
            )
        strategy_labels = {
            ChunkingStrategy.SINGLE: "single (all notes in one topic)",
            ChunkingStrategy.BY_GROUP: "by_group (one topic per group)",
            ChunkingStrategy.BY_COMPONENT: "by_component (one topic per Jira component)",
        }
        return f"""## Workspace

You are working with a technical writer on the release notes for {product_name(job)}: "{release_title(job)}".
The notes below are the current state. Topics: {len(job.topics)}, chunking {strategy_labels.get(job.chunking_strategy, job.chunking_strategy)}.
Groups in order: {', '.join(groups) if groups else '(none yet)'}.

## Notes (id | group | status | headline — summary [Jira issues])

{chr(10).join(lines) if lines else '(no notes yet)'}{selected_block}

## How to work

- Make changes with the tools; do not paste DITA into your reply unless the person asks to see it.
  Several tool calls can be made in one turn. Afterwards, reply with a short plain-language
  summary of what you changed (or what you found), using the notes' headlines, not their ids.
- Change only what was asked. If the request is ambiguous, ask instead of guessing.
- "This note" / "this one" means the note the person is looking at, when there is one.
- When you rewrite content, read the note first unless you already have its fragment, keep the
  facts true to its Jira issues, and send the COMPLETE fragment to update_note.
- Statuses: draft, review, approved, rejected (rejected notes are left out of the output).
- When asked to split or reorganize the release notes into topics, use reorganize_topics.

{FRAGMENT_FORMAT}"""

    def _fallback_reply(self) -> str:
        if not self.actions:
            return "I couldn't complete that request. Could you rephrase it?"
        done = [a for a in self.actions if a.get("ok")]
        if not done:
            return "I tried to make the change but it did not go through: " + "; ".join(
                str(a.get("result"))[:200] for a in self.actions[:3]
            )
        return "Done: " + "; ".join(a.get("description", a.get("tool", "")) for a in done)

    # ── Tools ────────────────────────────────────────────────────────────────────────

    def _find_item(self, ref: str) -> Optional[ReleaseNoteItem]:
        ref = (ref or "").strip().lower()
        if not ref:
            return None
        for item in self.job.items:
            sid = str(item.id).lower()
            if ref in (sid, item.fragment_id.lower(), sid.split("-")[0]) or (len(ref) >= 8 and sid.startswith(ref)):
                return item
        return None

    def _executor(self, permitted_urls: List[str]) -> Callable:
        async def execute(tool_name: str, args: dict) -> str:
            handler = getattr(self, f"_tool_{tool_name}", None)
            if tool_name == "read_url":
                url = (args.get("url") or "").strip()
                result = await fetch_url(url, list(permitted_urls))
                self._log(tool_name, args, result.ok, "fetched" if result.ok else (result.blocked_reason or "blocked"))
                return result.content or f"Could not fetch {url}: {result.blocked_reason}" if not result.ok else (result.content or "No readable content.")
            if handler is None:
                self._log(tool_name, args, False, "unknown tool")
                return f"Unknown tool: {tool_name!r}"
            try:
                return handler(args or {})
            except FragmentError as exc:
                detail = "The fragment is not valid DITA: " + "; ".join(exc.errors[:5])
                self._log(tool_name, args, False, detail)
                return detail
            except Exception as exc:
                logger.warning("Chat tool %s failed: %s", tool_name, exc, exc_info=True)
                self.db.rollback()
                self._log(tool_name, args, False, f"error: {exc}")
                return f"The tool failed: {exc}"
        return execute

    def _log(self, tool: str, args: dict, ok: bool, result: str, description: Optional[str] = None) -> None:
        trimmed = {k: _short(v, 200) for k, v in (args or {}).items()}
        self.actions.append({"tool": tool, "args": trimmed, "ok": ok, "result": _short(result, 300),
                             "description": description or result})

    def _tool_read_note(self, args: dict) -> str:
        item = self._find_item(args.get("note_id", ""))
        if item is None:
            self._log("read_note", args, False, "no such note")
            return "No note with that id. Use the ids listed in the workspace."
        self._log("read_note", args, True, f"read {item.title}", f"Read “{item.title}”")
        return json.dumps({
            "id": item.fragment_id, "title": item.title, "summary": item.summary, "group": item.group_name,
            "status": item.status, "dita_content": item.dita_content,
            "issues": [issue_record(link.issue) for link in item.issue_links],
        }, ensure_ascii=False, indent=1)

    def _tool_read_issue(self, args: dict) -> str:
        key = (args.get("issue_key") or "").strip().upper()
        issue = next((i for i in self.job.issues if i.issue_key.upper() == key), None)
        if issue is None:
            self._log("read_issue", args, False, "no such issue")
            return f"{key} is not part of this job."
        self._log("read_issue", args, True, f"read {key}", f"Read {key}")
        record = issue_record(issue, description_limit=6000, comment_limit=1500, max_comments=20)
        record.update({"url": issue.url, "relevance": issue.relevance, "relevance_reason": issue.relevance_reason,
                       "in_query": issue.in_query})
        return json.dumps(record, ensure_ascii=False, indent=1)

    def _tool_update_note(self, args: dict) -> str:
        item = self._find_item(args.get("note_id", ""))
        if item is None:
            self._log("update_note", args, False, "no such note")
            return "No note with that id."
        changes = []
        title = (args.get("title") or "").strip()
        summary = args.get("summary")
        if title and title != item.title:
            previous = item.title
            item.title = title[:500]
            record_history(self.db, item, HistoryEvent.CONTENT_EDITED, f"Headline changed from “{previous}” to “{item.title}”",
                           actor="agent", details={"field": "title", "from": previous, "to": item.title})
            changes.append("headline")
        if summary is not None and summary.strip() != (item.summary or "").strip():
            previous = item.summary
            item.summary = summary.strip()
            record_history(self.db, item, HistoryEvent.CONTENT_EDITED, "Summary rewritten by the agent",
                           actor="agent", details={"field": "summary", "from": previous, "to": item.summary})
            changes.append("summary")
        dita = args.get("dita_content")
        if dita and dita.strip():
            if set_item_content(self.db, item, dita, actor="agent", validator=self.validator):
                changes.append("content")
        if not changes:
            self._log("update_note", args, True, "nothing changed", f"No change to “{item.title}”")
            return "Nothing changed (the values were the same)."
        self.changed_items.add(item.id)
        self.db.flush()
        self._log("update_note", args, True, "updated " + ", ".join(changes), f"Updated {', '.join(changes)} of “{item.title}”")
        return f"Updated {', '.join(changes)} of “{item.title}”."

    def _tool_set_note_status(self, args: dict) -> str:
        item = self._find_item(args.get("note_id", ""))
        status = (args.get("status") or "").strip().lower()
        if item is None:
            self._log("set_note_status", args, False, "no such note")
            return "No note with that id."
        if status not in ItemStatus.ALL:
            self._log("set_note_status", args, False, "bad status")
            return f"Status must be one of {', '.join(ItemStatus.ALL)}."
        if item.status == status:
            self._log("set_note_status", args, True, "unchanged", f"“{item.title}” already {status}")
            return f"“{item.title}” is already {status}."
        previous = item.status
        item.status = status
        record_history(self.db, item, HistoryEvent.STATUS_CHANGED, f"Status changed from {previous} to {status}",
                       actor="agent", details={"from": previous, "to": status})
        self.changed_items.add(item.id)
        self.db.flush()
        self._log("set_note_status", args, True, f"{previous} → {status}", f"Set “{item.title}” to {status}")
        return f"“{item.title}” is now {status}."

    def _tool_move_note(self, args: dict) -> str:
        item = self._find_item(args.get("note_id", ""))
        if item is None:
            self._log("move_note", args, False, "no such note")
            return "No note with that id."
        group = args.get("group_name")
        position = args.get("position")
        try:
            position = int(position) if position is not None else None
        except (TypeError, ValueError):
            position = None
        previous_group = item.group_name
        move_item(self.job, item, group, position)
        where = f"to group “{item.group_name}”" if group and group != previous_group else "within its group"
        if position:
            where += f" at position {position}"
        record_history(self.db, item, HistoryEvent.MOVED, f"Moved {where}", actor="agent",
                       details={"from_group": previous_group, "to_group": item.group_name, "position": position})
        self.changed_items.add(item.id)
        self.db.flush()
        self._log("move_note", args, True, f"moved {where}", f"Moved “{item.title}” {where}")
        return f"Moved “{item.title}” {where}."

    def _tool_rename_group(self, args: dict) -> str:
        old = (args.get("old_name") or "").strip()
        new = (args.get("new_name") or "").strip()
        if not old or not new:
            self._log("rename_group", args, False, "names required")
            return "Both old_name and new_name are required."
        moved = [i for i in self.job.items if (i.group_name or "").strip() == old]
        if not moved:
            self._log("rename_group", args, False, "no such group")
            return f"No group named “{old}”."
        for item in moved:
            item.group_name = new
            record_history(self.db, item, HistoryEvent.MOVED, f"Group renamed from “{old}” to “{new}”",
                           actor="agent", details={"from_group": old, "to_group": new})
            self.changed_items.add(item.id)
        self.db.flush()
        self._log("rename_group", args, True, f"{len(moved)} notes", f"Renamed group “{old}” to “{new}”")
        return f"Renamed “{old}” to “{new}” ({len(moved)} notes)."

    def _tool_create_note(self, args: dict) -> str:
        title = (args.get("title") or "").strip()[:500]
        summary = (args.get("summary") or "").strip()
        if not title:
            self._log("create_note", args, False, "title required")
            return "A title is required."
        item = ReleaseNoteItem(
            job_id=self.job.id, position=max((i.position for i in self.job.items), default=-1) + 1,
            group_name=(args.get("group_name") or "").strip() or None, title=title, summary=summary,
            dita_content="", status=ItemStatus.DRAFT,
        )
        self.db.add(item)
        self.job.items.append(item)
        self.db.flush()
        by_key = {i.issue_key.upper(): i for i in self.job.issues}
        linked = []
        for key in args.get("issue_keys") or []:
            issue = by_key.get(str(key).strip().upper())
            if issue is not None and issue.issue_key not in linked:
                self.db.add(ReleaseNoteItemIssue(item_id=item.id, issue_id=issue.id))
                linked.append(issue.issue_key)
        self.db.flush()
        self.db.refresh(item)
        dita = args.get("dita_content")
        if dita and dita.strip():
            item.dita_content = coerce_fragment(dita, item.fragment_id, item.title, self.validator)
        else:
            from app.services.topic_assembler import plain_text_fragment
            item.dita_content = plain_text_fragment(item.fragment_id, item.title, item.summary)
        record_history(self.db, item, HistoryEvent.CREATED, "Created by the agent in chat", actor="agent",
                       details={"issue_keys": linked})
        if item.group_name:
            move_item(self.job, item, item.group_name, None)
        self.changed_items.add(item.id)
        self.db.flush()
        self._log("create_note", args, True, f"created {item.fragment_id}", f"Created “{item.title}”")
        return f"Created “{item.title}” ({item.fragment_id})" + (f" linked to {', '.join(linked)}" if linked else "") + "."

    def _tool_reorganize_topics(self, args: dict) -> str:
        strategy = (args.get("strategy") or "").strip().lower()
        if strategy not in ChunkingStrategy.ALL:
            self._log("reorganize_topics", args, False, "bad strategy")
            return f"Strategy must be one of {', '.join(ChunkingStrategy.ALL)}."
        self._requested_strategy = strategy
        self.topics_changed = True
        self._log("reorganize_topics", args, True, strategy, f"Reorganized topics: {strategy}")
        return f"The notes will be re-split into topics using the {strategy} strategy."
