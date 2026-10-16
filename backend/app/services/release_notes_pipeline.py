"""The release-notes pipeline: Jira issues in, reviewed-ready notes and topics out.

Stages (docs/COLLABORATIVE_WORKFLOW.md): fetch issues → evaluate → consolidate → organize →
write → assemble → publish. The same code runs a first run and a rerun; the issue snapshot
decides how much of the work is new (see ``jira_snapshot``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from hop_core.dita import DitaValidator

from app.config import get_settings
from app.core.security import decrypt_credentials
from app.models.database import (
    Credential, CredentialType, HistoryEvent, InstructionSet, IssueRelevance, ItemStatus, Job,
    JobJiraIssue, JobRequest, JobStage, JobStatus, ReleaseNoteItem, ReleaseNoteItemIssue,
)
from app.services import pipeline_prompts as prompts
from app.services.agents import AgentUnavailable, ResolvedAgent, resolve_agent
from app.services.jira_service import JiraService
from app.services.jira_snapshot import SnapshotResult, describe_diff, sync_snapshot
from app.services.llm_json import extract_json
from app.services.topic_assembler import FragmentError, coerce_fragment, plain_text_fragment
from app.services.workspace_service import (
    PublishError, assemble_job_topics, find_decryptable_credential, group_order, product_name,
    publish_topics, record_history, renumber_positions,
)

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """A failure whose message is safe to show a person."""


class JobCancelled(Exception):
    """The person cancelled the job while it was running."""


EVALUATE_BATCH_SIZE = 12
WRITE_CONCURRENCY = 3


class ReleaseNotesPipeline:
    """Runs one job to completion, reporting progress on the job row."""

    def __init__(self, db: Session, job_id: UUID, validator: Optional[DitaValidator] = None):
        self.db = db
        self.job_id = job_id
        self.validator = validator or DitaValidator()
        self.job: Optional[Job] = None
        self.instruction_set: Optional[InstructionSet] = None
        self.writer: Optional[ResolvedAgent] = None
        self.analyst: Optional[ResolvedAgent] = None

    # ── Entry point ──────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        job = self.db.query(Job).filter(Job.id == self.job_id).first()
        if not job:
            logger.error("Job %s not found", self.job_id)
            return
        self.job = job

        try:
            self._start(job)
            self.instruction_set = job.instruction_set
            if self.instruction_set is None:
                raise PipelineError("The job's instruction set no longer exists.")

            self._resolve_agents(job)
            tickets = await self._fetch_issues(job)
            snapshot = sync_snapshot(self.db, job, tickets)
            job.tickets_processed = len(snapshot.seen)
            self.db.commit()
            self._log_snapshot(job, snapshot)

            self._apply_jira_changes(job, snapshot)
            self._check_cancelled(job)

            # New issues, issues back in the query, changed issues that never produced a note,
            # and issues an earlier run snapshotted but failed before judging.
            to_evaluate = []
            for issue in [
                *snapshot.new,
                *snapshot.returned,
                *[issue for issue, _ in snapshot.changed if not issue.item_links],
                *[issue for issue in snapshot.unchanged if issue.relevance == IssueRelevance.PENDING],
            ]:
                if issue not in to_evaluate:
                    to_evaluate.append(issue)
            candidates = await self._evaluate(job, to_evaluate)
            self._check_cancelled(job)

            new_items = await self._consolidate(job, candidates)
            self._check_cancelled(job)

            await self._organize(job, new_items)
            self._check_cancelled(job)

            to_regenerate = [
                item for item in job.items
                if getattr(item, "_regenerate_reason", None)
            ]
            await self._write(job, new_items, to_regenerate)
            self._check_cancelled(job)

            self._assemble(job)

            if job.auto_publish or (self.instruction_set and self.instruction_set.publish_to_heretto):
                await self._publish(job)

            job.status = JobStatus.COMPLETED
            job.stage = JobStage.DONE
            job.stage_message = self._done_message(job, snapshot, new_items, to_regenerate)
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = None
            self.db.commit()
            logger.info("Job %s completed", job.id)

        except JobCancelled:
            logger.info("Job %s cancelled", job.id)
            job.stage_message = "Cancelled"
            job.completed_at = datetime.now(timezone.utc)
            self.db.commit()
        except Exception as exc:
            logger.error("Job %s failed: %s", job.id, exc, exc_info=True)
            self.db.rollback()
            job = self.db.query(Job).filter(Job.id == self.job_id).first()
            if job is not None:
                job.status = JobStatus.FAILED
                job.error_message = sanitize_job_error(exc)
                job.completed_at = datetime.now(timezone.utc)
                self.db.commit()

    # ── Bookkeeping ──────────────────────────────────────────────────────────────────

    def _start(self, job: Job) -> None:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.completed_at = None
        job.error_message = None
        job.run_count = (job.run_count or 0) + 1
        job.last_run_at = job.started_at
        self._set_stage(job, JobStage.FETCH_ISSUES, "Fetching issues from Jira")

    def _set_stage(self, job: Job, stage: str, message: str) -> None:
        job.stage = stage
        job.stage_message = message
        self.db.commit()

    def _check_cancelled(self, job: Job) -> None:
        self.db.refresh(job, attribute_names=["status"])
        if job.status == JobStatus.CANCELLED:
            raise JobCancelled()

    def _log_request(self, job: Job, request_type: str, data: Dict[str, Any]) -> Tuple[JobRequest, float]:
        request = JobRequest(job_id=job.id, request_type=request_type, status="pending",
                             request_data=json.dumps(data, default=str))
        self.db.add(request)
        self.db.commit()
        return request, time.time()

    def _finish_request(self, request: JobRequest, started: float, response: Optional[Dict[str, Any]] = None,
                        error: Optional[str] = None) -> None:
        request.duration_ms = int((time.time() - started) * 1000)
        if error:
            request.status = "failed"
            request.error_message = error
        else:
            request.status = "success"
            request.response_data = json.dumps(response or {}, default=str)
        self.db.commit()

    def _log_snapshot(self, job: Job, snapshot: SnapshotResult) -> None:
        request, started = self._log_request(job, "issue_snapshot", {"run": job.run_count})
        self._finish_request(request, started, {
            "new": [i.issue_key for i in snapshot.new],
            "changed": [i.issue_key for i, _ in snapshot.changed],
            "unchanged": len(snapshot.unchanged),
            "returned": [i.issue_key for i in snapshot.returned],
            "removed": [i.issue_key for i in snapshot.removed],
        })

    @staticmethod
    def _done_message(job: Job, snapshot: SnapshotResult, new_items: Sequence[ReleaseNoteItem],
                      regenerated: Sequence[ReleaseNoteItem]) -> str:
        total = sum(1 for i in job.items if i.status != ItemStatus.REJECTED)
        if job.run_count <= 1:
            return f"{total} release note{'s' if total != 1 else ''} drafted from {len(snapshot.seen)} issues"
        parts = []
        if new_items:
            parts.append(f"{len(new_items)} new")
        if regenerated:
            parts.append(f"{len(regenerated)} rewritten")
        if snapshot.changed:
            parts.append(f"{len(snapshot.changed)} issue{'s' if len(snapshot.changed) != 1 else ''} changed")
        if snapshot.removed:
            parts.append(f"{len(snapshot.removed)} left the query")
        return "Rerun: " + (", ".join(parts) if parts else "no changes in Jira")

    # ── Stage 0: agents and Jira ─────────────────────────────────────────────────────

    def _resolve_agents(self, job: Job) -> None:
        instruction_set = self.instruction_set
        try:
            self.writer = resolve_agent(self.db, instruction_set.writer_agent, job.organization_id, "writer")
            if instruction_set.analysis_agent is not None:
                self.analyst = resolve_agent(self.db, instruction_set.analysis_agent, job.organization_id, "analysis")
            else:
                self.analyst = self.writer
        except AgentUnavailable as exc:
            raise PipelineError(str(exc)) from exc

    def _jira_config(self, job: Job) -> dict:
        instruction_set = self.instruction_set
        if instruction_set and instruction_set.jira_credential_id:
            cred = self.db.query(Credential).filter(
                Credential.id == instruction_set.jira_credential_id,
                or_(Credential.user_id == job.user_id, Credential.organization_id == job.organization_id),
            ).first()
            if not cred:
                raise PipelineError(
                    f"The instruction set's selected Jira credential {instruction_set.jira_credential_id} was not found"
                )
            try:
                return decrypt_credentials(cred.encrypted_data)
            except Exception:
                raise PipelineError(f"Failed to decrypt Jira credential '{cred.name}'. It may need to be re-created.")
        cred, config = find_decryptable_credential(self.db, job.user_id, job.organization_id, CredentialType.JIRA)
        if not cred:
            raise PipelineError("No Jira credentials found. Please add Jira credentials in the Credentials page.")
        return config

    async def _fetch_issues(self, job: Job):
        config = self._jira_config(job)
        settings = get_settings()
        max_results = min(job.max_tickets or 100, settings.max_tickets_per_job)
        request, started = self._log_request(job, "jira_query", {
            "jql": job.jql_query, "server": config["server_url"], "max_tickets": max_results,
        })
        service = JiraService(server=config["server_url"], email=config["email"], api_token=config["api_token"])
        try:
            tickets = await service.execute_query(job.jql_query, max_results=max_results)
        except Exception as exc:
            self._finish_request(request, started, error=str(exc))
            raise PipelineError(str(exc)) from exc
        self._finish_request(request, started, {"ticket_count": len(tickets), "tickets": [t.key for t in tickets[:25]]})
        if not tickets and not job.issues:
            raise PipelineError("No tickets found matching JQL query")
        return tickets

    # ── Stage 1b: what a rerun does with changed and removed issues ──────────────────

    def _apply_jira_changes(self, job: Job, snapshot: SnapshotResult) -> None:
        now = datetime.now(timezone.utc)
        for issue, changes in snapshot.changed:
            summary = describe_diff(changes) or "Issue content changed"
            for link in issue.item_links:
                item = link.item
                record_history(
                    self.db, item, HistoryEvent.JIRA_CHANGED,
                    f"{issue.issue_key} changed in Jira: {summary}",
                    details={"issue_key": issue.issue_key, "changes": changes},
                )
                untouched = not item.user_edited and item.status in (ItemStatus.DRAFT, ItemStatus.REVIEW)
                if untouched:
                    # Rewrite it below; keep the reason so history can say why.
                    reasons = getattr(item, "_regenerate_reason", []) or []
                    reasons.append(f"{issue.issue_key}: {summary}")
                    item._regenerate_reason = reasons
                else:
                    item.needs_attention = True
                    item.attention_reason = (
                        f"{issue.issue_key} changed in Jira after this note was "
                        f"{'edited' if item.user_edited else item.status}: {summary}"
                    )
                    record_history(
                        self.db, item, HistoryEvent.FLAGGED,
                        f"Flagged for review: {issue.issue_key} changed after the note was {'edited' if item.user_edited else item.status}",
                        details={"issue_key": issue.issue_key},
                    )
        for issue in snapshot.removed:
            for link in issue.item_links:
                item = link.item
                item.needs_attention = True
                item.attention_reason = f"{issue.issue_key} no longer matches the job's JQL query"
                record_history(
                    self.db, item, HistoryEvent.ISSUE_REMOVED,
                    f"{issue.issue_key} no longer matches the query",
                    details={"issue_key": issue.issue_key},
                )
        for issue in snapshot.returned:
            for link in issue.item_links:
                item = link.item
                record_history(
                    self.db, item, HistoryEvent.FLAGGED,
                    f"{issue.issue_key} matches the query again",
                    details={"issue_key": issue.issue_key},
                )
        job.stage_message = f"{len(snapshot.seen)} issues; {len(snapshot.new)} new, {len(snapshot.changed)} changed"
        self.db.commit()

    # ── Stage 2: evaluate ────────────────────────────────────────────────────────────

    async def _evaluate(self, job: Job, issues: Sequence[JobJiraIssue]) -> List[dict]:
        """Decide relevance per issue and collect candidate notes with their issue keys."""
        if not issues:
            self._set_stage(job, JobStage.EVALUATE, "No new issues to evaluate")
            return []
        product = product_name(job)
        instructions = prompts.evaluate_instructions(product, self.instruction_set.relevance_guidance)
        by_key = {issue.issue_key: issue for issue in issues}
        candidates: List[dict] = []
        total = len(issues)

        for start in range(0, total, EVALUATE_BATCH_SIZE):
            batch = list(issues[start:start + EVALUATE_BATCH_SIZE])
            self._set_stage(job, JobStage.EVALUATE,
                            f"Evaluating issues {start + 1}–{min(start + len(batch), total)} of {total}")
            request, started = self._log_request(job, "evaluate", {
                "agent": self.analyst.name, "issues": [i.issue_key for i in batch],
            })
            try:
                result = await self.analyst.run(instructions, prompts.issues_json(batch), max_tokens=8192)
                parsed = extract_json(result.output)
            except Exception as exc:
                self._finish_request(request, started, error=str(exc))
                raise PipelineError(f"Evaluating issues failed: {exc}") from exc

            decided = 0
            for record in (parsed.get("issues") if isinstance(parsed, dict) else parsed) or []:
                if not isinstance(record, dict):
                    continue
                issue = by_key.get(str(record.get("key", "")).strip())
                if issue is None:
                    continue
                decided += 1
                notes = [n for n in (record.get("notes") or []) if isinstance(n, dict) and n.get("title")]
                relevant = bool(record.get("relevant")) and bool(notes)
                issue.relevance = IssueRelevance.RELEVANT if relevant else IssueRelevance.NOT_RELEVANT
                issue.relevance_reason = (record.get("reason") or "").strip() or None
                for note in notes:
                    candidates.append({
                        "title": str(note.get("title", "")).strip()[:500],
                        "summary": str(note.get("summary", "")).strip(),
                        "category": (str(note.get("category", "")).strip() or None),
                        "issue_keys": [issue.issue_key],
                    })
            # Anything the model skipped stays pending so a person can see it was not judged.
            for issue in batch:
                if issue.relevance == IssueRelevance.PENDING:
                    issue.relevance = IssueRelevance.NOT_RELEVANT
                    issue.relevance_reason = "The analysis agent did not return a decision for this issue"
            self._finish_request(request, started, {
                "decided": decided, "candidates": len(candidates), "provider": result.provider, "model": result.model,
            })
            self._check_cancelled(job)
        return candidates

    # ── Stage 3: consolidate ─────────────────────────────────────────────────────────

    async def _consolidate(self, job: Job, candidates: List[dict]) -> List[ReleaseNoteItem]:
        if not candidates:
            self._set_stage(job, JobStage.CONSOLIDATE, "No new release notes to create")
            return []
        self._set_stage(job, JobStage.CONSOLIDATE, f"Consolidating {len(candidates)} candidate notes")
        final: List[dict]
        if len(candidates) == 1:
            final = candidates
        else:
            request, started = self._log_request(job, "consolidate", {
                "agent": self.analyst.name, "candidates": len(candidates),
            })
            try:
                result = await self.analyst.run(
                    prompts.CONSOLIDATE_INSTRUCTIONS, prompts.candidates_json(candidates), max_tokens=8192, temperature=0.2,
                )
                parsed = extract_json(result.output)
                final = [
                    item for item in ((parsed.get("items") if isinstance(parsed, dict) else parsed) or [])
                    if isinstance(item, dict) and item.get("title")
                ]
                if not final:
                    raise ValueError("The model returned no items")
                self._finish_request(request, started, {"items": len(final), "provider": result.provider, "model": result.model})
            except Exception as exc:
                # Consolidation is a refinement; fall back to the candidates as they are.
                logger.warning("Consolidation failed for job %s, using candidates as-is: %s", job.id, exc)
                self._finish_request(request, started, error=f"{exc} (continuing with unconsolidated candidates)")
                final = candidates

        issues_by_key = {issue.issue_key: issue for issue in job.issues}
        known_keys = {k for c in candidates for k in c.get("issue_keys", [])}
        next_position = (max((i.position for i in job.items), default=-1) + 1)
        created: List[ReleaseNoteItem] = []
        for record in final:
            keys = [str(k).strip() for k in (record.get("issue_keys") or []) if str(k).strip() in issues_by_key]
            if not keys:
                # The model invented or mangled keys; keep the note but tie it to every candidate key.
                keys = [k for k in known_keys if k in issues_by_key][:1] or []
            item = ReleaseNoteItem(
                job_id=job.id,
                position=next_position,
                group_name=(str(record.get("category") or "").strip() or None),
                title=str(record.get("title", "")).strip()[:500] or "Untitled change",
                summary=str(record.get("summary", "")).strip(),
                dita_content="",
                status=ItemStatus.DRAFT,
            )
            next_position += 1
            self.db.add(item)
            job.items.append(item)
            self.db.flush()
            for key in dict.fromkeys(keys):
                self.db.add(ReleaseNoteItemIssue(item_id=item.id, issue_id=issues_by_key[key].id))
            self.db.flush()
            self.db.refresh(item)
            record_history(
                self.db, item, HistoryEvent.CREATED,
                f"Created from {', '.join(keys) if keys else 'the evaluation'} (run {job.run_count})",
                details={"issue_keys": keys, "run": job.run_count},
            )
            created.append(item)
        self.db.commit()
        return created

    # ── Stage 4: organize ────────────────────────────────────────────────────────────

    async def _organize(self, job: Job, new_items: List[ReleaseNoteItem]) -> None:
        if not new_items:
            self._set_stage(job, JobStage.ORGANIZE, "Nothing new to organize")
            return
        existing_groups = [g for g in group_order(job) if g] if job.run_count > 1 else []
        existing_groups = [
            g for g in existing_groups
            if any(i.group_name == g for i in job.items if i not in new_items)
        ]
        self._set_stage(job, JobStage.ORGANIZE, f"Organizing {len(new_items)} release notes")
        request, started = self._log_request(job, "organize", {
            "agent": self.analyst.name, "items": len(new_items), "existing_groups": existing_groups,
        })
        placement: Dict[int, Tuple[str, int, int]] = {}
        group_sequence: List[str] = list(existing_groups)
        try:
            result = await self.analyst.run(
                prompts.organize_instructions(self.instruction_set.organization_guidance, existing_groups),
                prompts.organize_input(new_items), max_tokens=4096, temperature=0.2,
            )
            parsed = extract_json(result.output)
            groups = (parsed.get("groups") if isinstance(parsed, dict) else parsed) or []
            for group_index, group in enumerate(groups):
                if not isinstance(group, dict):
                    continue
                name = str(group.get("name") or "").strip() or "Other changes"
                if name not in group_sequence:
                    group_sequence.append(name)
                for order, number in enumerate(group.get("notes") or []):
                    try:
                        n = int(number)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= n <= len(new_items) and n not in placement:
                        placement[n] = (name, group_sequence.index(name), order)
            self._finish_request(request, started, {
                "groups": group_sequence, "placed": len(placement), "provider": result.provider, "model": result.model,
            })
        except Exception as exc:
            logger.warning("Organizing failed for job %s, using categories as groups: %s", job.id, exc)
            self._finish_request(request, started, error=f"{exc} (continuing with the evaluation's categories)")

        # Notes the model did not place keep their category as their group.
        for n, item in enumerate(new_items, start=1):
            if n not in placement:
                name = (item.group_name or "Other changes").strip()
                if name not in group_sequence:
                    group_sequence.append(name)
                placement[n] = (name, group_sequence.index(name), 10_000 + n)

        base = max((i.position for i in job.items), default=-1) + 1
        for n, item in enumerate(new_items, start=1):
            name, group_rank, order = placement[n]
            item.group_name = name
            item.position = base + group_rank * 1000 + order
        renumber_positions(job, group_sequence)
        self.db.commit()

    # ── Stage 5: write ───────────────────────────────────────────────────────────────

    async def _write(self, job: Job, new_items: List[ReleaseNoteItem], regenerate: List[ReleaseNoteItem]) -> None:
        work: List[Tuple[ReleaseNoteItem, bool]] = [(i, False) for i in new_items] + [(i, True) for i in regenerate]
        if not work:
            self._set_stage(job, JobStage.WRITE, "Nothing to write")
            return
        total = len(work)
        done = 0
        self._set_stage(job, JobStage.WRITE, f"Writing release notes (0 of {total})")
        semaphore = asyncio.Semaphore(WRITE_CONCURRENCY)
        product = product_name(job)
        # The instruction set's guidance reaches the writer, not just the organize stage:
        # it is where people put how a note should read, and the writer is what writes it.
        guidance = self.instruction_set.organization_guidance if self.instruction_set else None
        instructions = prompts.write_instructions(product, guidance)

        async def generate(item: ReleaseNoteItem, is_rewrite: bool) -> Tuple[ReleaseNoteItem, bool, str, Optional[str]]:
            """Returns (item, is_rewrite, fragment, fallback_reason)."""
            async with semaphore:
                if is_rewrite:
                    reasons = getattr(item, "_regenerate_reason", []) or []
                    input_text = prompts.regenerate_input(item, "; ".join(reasons))
                else:
                    input_text = prompts.write_input(item)
                errors: List[str] = []
                last_output = ""
                for attempt in range(2):
                    task = instructions if attempt == 0 else prompts.rewrite_instructions(product, errors, guidance)
                    payload = input_text if attempt == 0 else prompts.write_input(item, previous_fragment=last_output)
                    request, started = self._log_request(job, "write", {
                        "agent": self.writer.name, "item_id": str(item.id), "title": item.title,
                        "attempt": attempt + 1, "rewrite": is_rewrite,
                    })
                    try:
                        result = await self.writer.run(task, payload, max_tokens=4096)
                    except Exception as exc:
                        self._finish_request(request, started, error=str(exc))
                        raise PipelineError(f"Writing '{item.title}' failed: {exc}") from exc
                    last_output = result.output
                    try:
                        fragment = coerce_fragment(result.output, item.fragment_id, item.title, self.validator)
                    except FragmentError as exc:
                        errors = exc.errors
                        self._finish_request(request, started, error="Invalid DITA: " + "; ".join(errors[:3]))
                        continue
                    self._finish_request(request, started, {
                        "content_length": len(fragment), "provider": result.provider, "model": result.model,
                    })
                    return item, is_rewrite, fragment, None
                return item, is_rewrite, plain_text_fragment(item.fragment_id, item.title, item.summary), "; ".join(errors[:3])

        results = await asyncio.gather(*(generate(item, rewrite) for item, rewrite in work), return_exceptions=True)
        failures = [r for r in results if isinstance(r, Exception)]
        for outcome in results:
            if isinstance(outcome, Exception):
                continue
            item, is_rewrite, fragment, fallback = outcome
            previous = item.dita_content
            item.dita_content = fragment
            if is_rewrite:
                reasons = getattr(item, "_regenerate_reason", []) or []
                record_history(
                    self.db, item, HistoryEvent.REGENERATED,
                    "Rewritten after its Jira issue changed: " + "; ".join(reasons),
                    details={"previous_dita": previous, "reasons": reasons},
                )
            if fallback:
                item.needs_attention = True
                item.attention_reason = f"The writer could not produce valid DITA; the summary was used instead ({fallback})"
                record_history(
                    self.db, item, HistoryEvent.FLAGGED,
                    "Writer output was not valid DITA; plain summary used",
                    details={"errors": fallback},
                )
            done += 1
        job.stage_message = f"Writing release notes ({done} of {total})"
        self.db.commit()
        if failures:
            raise failures[0]

    # ── Stage 6/7: assemble and publish ──────────────────────────────────────────────

    def _assemble(self, job: Job) -> None:
        self._set_stage(job, JobStage.ASSEMBLE, "Assembling DITA topics")
        strategy = job.chunking_strategy or (self.instruction_set.chunking_strategy if self.instruction_set else None)
        try:
            topics = assemble_job_topics(self.db, job, strategy, self.validator)
        except FragmentError as exc:
            raise PipelineError("DITA validation failed: " + "; ".join(exc.errors[:3])) from exc
        self.db.commit()
        job.stage_message = f"{len(topics)} topic{'s' if len(topics) != 1 else ''} assembled"
        self.db.commit()

    async def _publish(self, job: Job) -> None:
        self._set_stage(job, JobStage.PUBLISH, "Publishing to Heretto")
        try:
            results = await publish_topics(self.db, job)
        except PublishError as exc:
            # Publishing is a convenience step; the notes are done. Say so rather than fail.
            job.stage_message = f"Not published: {exc}"
            self.db.commit()
            return
        failed = [r for r in results if not r.success]
        if failed:
            job.stage_message = f"Published {len(results) - len(failed)} of {len(results)} topics; {failed[0].message}"
            self.db.commit()


# Messages that are safe to show to users (raised intentionally as PipelineError, or by the
# services with a person-readable prefix).
_SAFE_ERROR_PREFIXES = (
    "No Jira credentials found",
    "No tickets found",
    "No AI credentials found",
    "Failed to decrypt",
    "Jira query failed",
    "Failed to get projects",
    "Failed to get versions",
    "Failed to get issue",
    "DITA validation failed",
    "The instruction set",
    "The job's instruction set",
    "Agent '",
    "The writer agent",
    "The analysis agent",
    "Evaluating issues failed",
    "Writing '",
    "Anthropic returned HTTP",
    "OpenAI returned HTTP",
    "Gemini returned HTTP",
    "Google Gemini returned HTTP",
)


def sanitize_job_error(error) -> str:
    """Return a user-safe error message, stripping internal details."""
    message = str(error) if error is not None else ""
    if isinstance(error, PipelineError) and message:
        return message
    if not message:
        return "An unexpected error occurred while processing the job"
    for prefix in _SAFE_ERROR_PREFIXES:
        if message.startswith(prefix):
            return message
    return "An unexpected error occurred while processing the job — check the server logs for details"
