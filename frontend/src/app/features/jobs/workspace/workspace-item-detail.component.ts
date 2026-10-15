import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges, inject, ChangeDetectionStrategy } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar } from '@angular/material/snack-bar';
import {
  JobsService, ReleaseNoteItemDetail, ItemStatus, ITEM_STATUSES, ItemHistoryEntry, JobIssue
} from '../../../core/services/jobs.service';

type DetailTab = 'jira' | 'dita' | 'history';

interface NotePart {
  text: string;
  isLink: boolean;
}

const URL_PATTERN = /(https?:\/\/[^\s<>"]+)/g;

@Component({
  selector: 'app-workspace-item-detail',
  standalone: true,
  imports: [DatePipe, FormsModule, MatButtonModule, MatIconModule, MatTooltipModule, MatProgressSpinnerModule],
  template: `
    <div class="detail">
      @if (loading || !item) {
        <div class="loading"><mat-spinner diameter="28"></mat-spinner></div>
      } @else {
        <div class="detail-head">
          <div class="title-block">
            @if (editingTitle) {
              <input class="title-input" [(ngModel)]="titleDraft" (keydown.enter)="saveTitle()" (keydown.escape)="editingTitle = false" />
              <div class="title-actions">
                <button class="btn text" (click)="editingTitle = false">Cancel</button>
                <button class="btn primary" (click)="saveTitle()" [disabled]="!titleDraft.trim() || saving">Save</button>
              </div>
            } @else {
              <h3 (click)="startTitleEdit()" matTooltip="Click to rename">{{ item.title }}</h3>
            }
            <div class="head-meta">
              <span>{{ item.group_name || 'No group' }}</span>
              @for (key of item.issue_keys; track key; let last = $last) {
                <span>·</span>
                <span>
                  @if (issueUrl(key); as url) {
                    <a [href]="url" target="_blank" rel="noopener" class="issue-key">{{ key }}</a>
                  } @else {
                    <span class="issue-key">{{ key }}</span>
                  }{{ last ? '' : ',' }}
                </span>
              }
              @if (item.user_edited) { <span>· edited</span> }
            </div>
          </div>
          <button class="icon-btn" matTooltip="Back to chat" (click)="closed.emit()"><mat-icon>close</mat-icon></button>
        </div>

        <div class="detail-scroll">
          <div class="status-row">
            <label class="field status-field">Status
              <select [ngModel]="item.status" (ngModelChange)="setStatus($event)" [disabled]="saving || disabled">
                @for (status of statuses; track status.value) {
                  <option [value]="status.value">{{ status.label }}</option>
                }
              </select>
            </label>
            <label class="field group-field">Group
              <input [(ngModel)]="groupDraft" (blur)="saveGroup()" (keydown.enter)="blurTarget($event)" [disabled]="saving || disabled" list="groups">
              <datalist id="groups">
                @for (group of groups; track group) { <option [value]="group"></option> }
              </datalist>
            </label>
          </div>

          <div class="notes-block">
            <span class="field-label">Notes</span>
            @if (notesEditing) {
              <div>
                <textarea class="notes-editor" [(ngModel)]="notesDraft" rows="5"
                          placeholder="Context, open questions, links to a Slack thread or design doc…" [disabled]="saving"></textarea>
                <div class="row-actions">
                  <button class="btn text" (click)="notesEditing = false">Cancel</button>
                  <button class="btn primary" (click)="saveNotes()" [disabled]="saving">Save</button>
                </div>
              </div>
            } @else if (item.notes) {
              <div class="notes-view">
                @for (part of noteParts; track $index) {
                  @if (part.isLink) {
                    <a [href]="part.text" target="_blank" rel="noopener">{{ part.text }}</a>
                  } @else {
                    <span>{{ part.text }}</span>
                  }
                }
              </div>
              <div class="row-actions">
                <button class="btn" (click)="editNotes()" [disabled]="disabled">Edit notes</button>
              </div>
            } @else {
              <button class="notes-add" (click)="editNotes()" [disabled]="disabled">Add notes — context, open questions, links…</button>
            }
          </div>

          @if (item.needs_attention) {
            <div class="attention-banner">
              <svg class="flag-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/></svg>
              <div class="attention-text">
                <strong>Needs attention</strong>
                <div>{{ item.attention_reason }}</div>
              </div>
              <button class="btn text warn" (click)="clearAttention()" [disabled]="saving">Clear</button>
            </div>
          }

          <div class="dtabs">
            <button class="dtab" [class.active]="tab === 'jira'" (click)="tab = 'jira'">Jira</button>
            <button class="dtab" [class.active]="tab === 'dita'" (click)="tab = 'dita'">DITA</button>
            <button class="dtab" [class.active]="tab === 'history'" (click)="tab = 'history'">History ({{ item.history.length }})</button>
          </div>

          <div class="tab-body">
            @if (tab === 'jira') {
              <p class="summary">{{ item.summary }}</p>
              @if (item.issues.length === 0) {
                <p class="muted">This note is not linked to a Jira issue.</p>
              }
              @for (issue of item.issues; track issue.id) {
                <div class="issue-card" [class.dropped]="!issue.in_query">
                  <div class="issue-head">
                    <a [href]="issue.url" target="_blank" rel="noopener" class="issue-key">
                      {{ issue.issue_key }}<mat-icon class="inline-icon">open_in_new</mat-icon>
                    </a>
                    @if (issue.issue_type) { <span class="chip">{{ issue.issue_type }}</span> }
                    @if (issue.status) { <span class="chip" [class.chip-success]="isDone(issue)">{{ issue.status }}</span> }
                    @if (issue.item_ids.length > 1) {
                      <span class="chip chip-warning" matTooltip="This issue feeds several release notes">{{ issue.item_ids.length }} notes</span>
                    }
                    @if (!issue.in_query) {
                      <span class="chip chip-error">Left the query</span>
                    }
                  </div>
                  <div class="issue-summary">{{ issue.summary }}</div>
                  @if (issue.description) {
                    <details class="flat">
                      <summary>Description</summary>
                      <pre class="issue-text">{{ issue.description }}</pre>
                    </details>
                  }
                  @if (issue.comments.length) {
                    <details class="flat">
                      <summary>Comments ({{ issue.comments.length }})</summary>
                      @for (comment of issue.comments; track $index) {
                        <pre class="issue-text comment">{{ comment }}</pre>
                      }
                    </details>
                  }
                  <div class="issue-meta">{{ issueMeta(issue) }}</div>
                  @if (issue.relevance_reason) {
                    <div class="reason"><span class="why">Why</span><span>{{ issue.relevance_reason }}</span></div>
                  }
                </div>
              }
            }

            @if (tab === 'dita') {
              <textarea class="dita-editor" [(ngModel)]="ditaDraft" spellcheck="false" [disabled]="saving || disabled"></textarea>
              @if (ditaErrors.length) {
                <ul class="errors">
                  @for (error of ditaErrors; track $index) { <li>{{ error }}</li> }
                </ul>
              }
              <div class="editor-actions">
                <span class="muted hint">One <code>&lt;div outputclass="release-note"&gt;</code>; validated against DITA 1.3 on save</span>
                <button class="btn text" (click)="resetDita()" [disabled]="!ditaDirty || saving">Reset</button>
                <button class="btn primary" (click)="saveDita()" [disabled]="!ditaDirty || saving">Save</button>
              </div>
            }

            @if (tab === 'history') {
              <ol class="timeline">
                @for (entry of item.history; track entry.id) {
                  <li class="event" [class.warn]="isWarning(entry)">
                    <span class="event-icon">{{ historyGlyph(entry) }}</span>
                    <div class="event-body">
                      <div class="event-summary">{{ entry.summary }}</div>
                      <div class="muted">{{ actorLabel(entry) }} · {{ entry.created_at | date:'medium' }}</div>
                      @if (entry.details?.['changes']) {
                        @for (change of changesOf(entry); track change.label) {
                          <div class="diff">
                            <strong>{{ change.label }}</strong>
                            @if (change.added) {
                              {{ change.added.length }} new comment(s)
                              @for (comment of change.added; track $index) { <pre class="issue-text comment">{{ comment }}</pre> }
                            } @else {
                              <span class="from">{{ fmt(change.from) }}</span> <span class="to">{{ fmt(change.to) }}</span>
                            }
                          </div>
                        }
                      }
                      @if (entry.details?.['previous_dita']) {
                        <details class="flat">
                          <summary>Previous content</summary>
                          <pre class="issue-text mono">{{ entry.details!['previous_dita'] }}</pre>
                          <button class="btn text small" (click)="restorePrevious(entry.details!['previous_dita'])" [disabled]="saving || disabled">Restore this version</button>
                        </details>
                      }
                    </div>
                  </li>
                }
              </ol>
            }
          </div>
        </div>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    :host { display: block; height: 100%; min-height: 0; }
    .detail { display: flex; flex-direction: column; height: 100%; min-height: 0; font-size: 14px; }
    .loading { display: flex; justify-content: center; padding: 40px; }
    .muted { color: var(--text-tertiary); font-size: 12px; }

    /* ── Controls ── */
    .btn { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 12px; border-radius: 6px; border: 1px solid var(--border-default); background: var(--bg-primary); color: var(--text-primary); font: 600 13px/1 inherit; font-family: inherit; cursor: pointer; white-space: nowrap; }
    .btn:hover { background: var(--bg-secondary); border-color: var(--border-strong); }
    .btn.primary { background: var(--color-primary); border-color: var(--color-primary); color: var(--text-inverse); }
    .btn.primary:hover { background: var(--color-primary-hover); border-color: var(--color-primary-hover); }
    .btn.text { border-color: transparent; background: transparent; color: var(--color-primary); }
    .btn.text:hover { background: var(--bg-secondary); }
    .btn.text.warn { color: var(--color-warning-text); font-size: 12px; height: 26px; padding: 0 10px; }
    .btn.text.warn:hover { background: rgba(0, 0, 0, 0.06); }
    .btn.small { font-size: 12px; height: 26px; padding: 0 10px; margin: 0 6px 6px; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .icon-btn { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; padding: 0; border: none; border-radius: 6px; background: transparent; color: var(--text-secondary); cursor: pointer; flex-shrink: 0; }
    .icon-btn:hover { background: var(--bg-secondary); color: var(--text-primary); }
    .icon-btn mat-icon { font-size: 16px; width: 16px; height: 16px; }
    .inline-icon { font-size: 11px; width: 11px; height: 11px; vertical-align: middle; }
    .flag-icon { width: 16px; height: 16px; fill: none; stroke: var(--color-warning); stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; flex-shrink: 0; margin-top: 2px; }
    .row-actions { display: flex; justify-content: flex-end; gap: 6px; margin-top: 6px; }

    /* ── Head ── */
    .detail-head { display: flex; align-items: flex-start; gap: 8px; padding: 12px 16px 10px; border-bottom: 1px solid var(--border-light); flex-shrink: 0; }
    .title-block { flex: 1; min-width: 0; }
    .title-block h3 { margin: 0; font-size: 16px; font-weight: 600; line-height: 1.3; cursor: text; }
    .title-input { width: 100%; font: inherit; font-size: 16px; font-weight: 600; padding: 4px 8px; border: 1px solid var(--border-focus); border-radius: 6px; box-sizing: border-box; }
    .title-actions { display: flex; justify-content: flex-end; gap: 4px; margin-top: 4px; }
    .head-meta { font-size: 12px; color: var(--text-tertiary); display: flex; flex-wrap: wrap; gap: 0 4px; align-items: center; }
    .issue-key { font-family: var(--font-mono); font-size: 12px; font-weight: 500; display: inline-flex; align-items: center; gap: 4px; }
    .detail-scroll { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; }

    /* ── Status / group / notes ── */
    .status-row { display: flex; gap: 8px; padding: 12px 16px 10px; }
    .field { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--text-tertiary); }
    .field-label { font-size: 12px; color: var(--text-tertiary); }
    .status-field { width: 150px; }
    .group-field { flex: 1; min-width: 0; }
    .field select, .field input { height: 36px; border: 1px solid var(--border-default); border-radius: 6px; padding: 0 10px; font: inherit; font-size: 14px; background: var(--bg-primary); color: var(--text-primary); outline: none; width: 100%; box-sizing: border-box; }
    .field input { box-shadow: var(--shadow-inset-sm, inset 0 1px 2px rgba(0, 0, 0, 0.05)); }
    .field input:focus, .field select:focus, .notes-editor:focus, .dita-editor:focus { border-color: var(--border-focus); box-shadow: var(--focus-ring); }
    .notes-block { padding: 4px 16px 12px; display: flex; flex-direction: column; gap: 3px; }
    .notes-editor { width: 100%; font: inherit; font-size: 13px; line-height: 1.5; border: 1px solid var(--border-default); border-radius: 6px; padding: 10px; resize: vertical; background: var(--bg-primary); color: var(--text-primary); outline: none; box-sizing: border-box; }
    .notes-view { font-size: 13px; line-height: 1.55; color: var(--text-primary); white-space: pre-wrap; word-break: break-word; padding: 10px 12px; border: 1px solid var(--border-light); border-radius: 6px; background: var(--bg-secondary); }
    .notes-add { width: 100%; text-align: left; font: inherit; font-size: 13px; line-height: 1.5; padding: 9px 12px; border: 1px dashed var(--border-default); border-radius: 6px; background: var(--bg-primary); color: var(--text-tertiary); cursor: pointer; }
    .notes-add:hover { border-color: var(--border-strong); color: var(--text-secondary); }
    .notes-add:disabled { cursor: not-allowed; opacity: 0.6; }

    /* ── Attention ── */
    .attention-banner { display: flex; align-items: flex-start; gap: 10px; margin: 0 16px 8px; padding: 10px 12px; background: var(--color-warning-bg); color: var(--color-warning-text); border-radius: 6px; font-size: 13px; }
    .attention-text { flex: 1; }
    .attention-text strong { font-weight: 600; }

    /* ── Tabs ── */
    .dtabs { display: flex; border-bottom: 1px solid var(--border-light); }
    .dtab { flex: 1; background: none; border: none; border-bottom: 2px solid transparent; margin-bottom: -1px; padding: 10px 4px; cursor: pointer; color: var(--text-tertiary); font: 500 13px/1 inherit; font-family: inherit; }
    .dtab.active { color: var(--color-primary); border-bottom-color: var(--color-accent); }
    .tab-body { padding: 12px 16px 16px; }

    /* ── Jira ── */
    .summary { margin: 0 0 12px; color: var(--text-secondary); font-size: 13px; }
    .issue-card { border: 1px solid var(--border-light); border-radius: 6px; padding: 10px 12px; margin-bottom: 10px; }
    .issue-card.dropped { opacity: 0.7; }
    .issue-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
    .issue-head .issue-key { font-size: 13px; }
    .chip { display: inline-flex; font-size: 11px; font-weight: 500; line-height: 1; padding: 4px 8px; border-radius: 999px; background: var(--bg-tertiary); color: var(--text-primary); }
    .chip-success { background: var(--color-success-bg); color: var(--color-success-text); }
    .chip-warning { background: var(--color-warning-bg); color: var(--color-warning-text); }
    .chip-error { background: var(--color-error-bg); color: var(--color-error-text); }
    .issue-summary { font-weight: 500; margin-bottom: 6px; font-size: 13px; }
    .issue-text { white-space: pre-wrap; word-break: break-word; font: inherit; font-size: 13px; margin: 0; padding: 0 10px 8px; color: var(--text-secondary); }
    .issue-text.comment { border-left: 2px solid var(--border-strong); padding: 0 0 0 8px; margin: 6px 10px; }
    .issue-text.mono { font-family: var(--font-mono); font-size: 12px; }
    .issue-meta { font-size: 12px; color: var(--text-tertiary); margin-top: 6px; }
    .reason { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; display: flex; gap: 6px; align-items: flex-start; }
    .why { display: inline-flex; font-size: 10px; font-weight: 600; line-height: 1; padding: 3px 6px; border-radius: 4px; background: var(--color-accent-bg); color: var(--color-accent-text); letter-spacing: 0.04em; text-transform: uppercase; flex-shrink: 0; }
    details.flat { border: 1px solid var(--border-light); border-radius: 6px; margin: 6px 0; }
    details.flat summary { padding: 7px 10px; font-size: 13px; cursor: pointer; }

    /* ── DITA ── */
    .dita-editor { width: 100%; min-height: 300px; font-family: var(--font-mono); font-size: 12px; line-height: 1.5; border: 1px solid var(--border-default); border-radius: 6px; padding: 10px; resize: vertical; background: var(--bg-primary); color: var(--text-primary); box-sizing: border-box; outline: none; }
    .errors { margin: 8px 0; padding: 8px 12px 8px 28px; background: var(--color-error-bg); color: var(--color-error-text); border-radius: 6px; font-size: 12px; }
    .editor-actions { display: flex; align-items: center; gap: 6px; margin-top: 8px; }
    .editor-actions .hint { flex: 1; }
    .editor-actions code { font-family: var(--font-mono); }

    /* ── History ── */
    .timeline { list-style: none; margin: 0; padding: 0; }
    .event { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
    .event-icon { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 50%; background: var(--bg-tertiary); color: var(--text-secondary); flex-shrink: 0; font: 600 10px/1 var(--font-mono); }
    .event.warn .event-icon { background: var(--color-warning-bg); color: var(--color-warning-text); }
    .event-body { flex: 1; min-width: 0; }
    .event-summary { font-size: 13px; }
    .diff { font-size: 12px; margin-top: 4px; padding-left: 12px; color: var(--text-secondary); }
    .diff strong { font-weight: 600; }
    .diff .from { color: var(--color-error-text); text-decoration: line-through; }
    .diff .to { color: var(--color-success-text); }
  `]
})
export class WorkspaceItemDetailComponent implements OnChanges {
  private jobsService = inject(JobsService);
  private snackBar = inject(MatSnackBar);

  @Input({ required: true }) jobId!: string;
  @Input({ required: true }) itemId!: string;
  @Input() groups: string[] = [];
  @Input() disabled = false;
  @Output() updated = new EventEmitter<ReleaseNoteItemDetail>();
  @Output() closed = new EventEmitter<void>();

  item: ReleaseNoteItemDetail | null = null;
  loading = true;
  saving = false;
  statuses = ITEM_STATUSES;
  tab: DetailTab = 'jira';

  editingTitle = false;
  titleDraft = '';
  groupDraft = '';
  ditaDraft = '';
  ditaErrors: string[] = [];
  notesEditing = false;
  notesDraft = '';

  get ditaDirty(): boolean {
    return !!this.item && this.ditaDraft.trim() !== (this.item.dita_content || '').trim();
  }

  /** The notes split into text and links, so links are clickable. */
  get noteParts(): NotePart[] {
    return (this.item?.notes || '').split(URL_PATTERN).filter(Boolean)
      .map(text => ({ text, isLink: /^https?:\/\//.test(text) }));
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['itemId'] || changes['jobId']) {
      this.load();
    }
  }

  load(): void {
    this.loading = true;
    this.jobsService.getItem(this.jobId, this.itemId).subscribe({
      next: (item) => {
        this.apply(item);
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.snackBar.open('Failed to load the note', 'Close', { duration: 3000 });
      }
    });
  }

  private apply(item: ReleaseNoteItemDetail): void {
    this.item = item;
    this.titleDraft = item.title;
    this.groupDraft = item.group_name || '';
    this.ditaDraft = item.dita_content;
    this.ditaErrors = [];
    this.editingTitle = false;
    this.notesEditing = false;
  }

  private save(update: Parameters<JobsService['updateItem']>[2], success?: string): void {
    if (!this.item || this.saving) return;
    this.saving = true;
    this.jobsService.updateItem(this.jobId, this.item.id, update).subscribe({
      next: (item) => {
        this.saving = false;
        this.apply(item);
        this.updated.emit(item);
        if (success) this.snackBar.open(success, 'Close', { duration: 2000 });
      },
      error: (error) => {
        this.saving = false;
        const detail = error.error?.detail;
        if (detail && typeof detail === 'object' && Array.isArray(detail.errors)) {
          this.ditaErrors = detail.errors;
        } else {
          this.snackBar.open(typeof detail === 'string' ? detail : 'Failed to save', 'Close', { duration: 5000 });
        }
      }
    });
  }

  issueUrl(key: string): string | null {
    return this.item?.issues.find(i => i.issue_key === key)?.url || null;
  }

  issueMeta(issue: JobIssue): string {
    const parts = [issue.priority, issue.assignee, issue.components.join(', ') || 'no component'];
    if (issue.fix_versions.length) parts.push(issue.fix_versions.join(', '));
    if (issue.jira_updated) parts.push(`updated ${new Date(issue.jira_updated).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}`);
    return parts.filter(Boolean).join(' · ');
  }

  blurTarget(event: Event): void {
    (event.target as HTMLElement | null)?.blur();
  }

  startTitleEdit(): void {
    if (this.disabled) return;
    this.titleDraft = this.item?.title || '';
    this.editingTitle = true;
  }

  saveTitle(): void {
    const title = this.titleDraft.trim();
    if (!title || title === this.item?.title) { this.editingTitle = false; return; }
    this.save({ title }, 'Headline updated');
  }

  setStatus(status: ItemStatus): void {
    if (status !== this.item?.status) this.save({ status });
  }

  saveGroup(): void {
    const group = this.groupDraft.trim();
    if (group !== (this.item?.group_name || '')) this.save({ group_name: group });
  }

  editNotes(): void {
    if (this.disabled) return;
    this.notesDraft = this.item?.notes || '';
    this.notesEditing = true;
  }

  saveNotes(): void {
    const notes = this.notesDraft.trim();
    if (notes === (this.item?.notes || '')) { this.notesEditing = false; return; }
    this.save({ notes }, 'Notes saved');
  }

  clearAttention(): void {
    this.save({ clear_attention: true });
  }

  saveDita(): void {
    if (!this.ditaDirty) return;
    this.ditaErrors = [];
    this.save({ dita_content: this.ditaDraft }, 'Content saved');
  }

  resetDita(): void {
    this.ditaDraft = this.item?.dita_content || '';
    this.ditaErrors = [];
  }

  restorePrevious(dita: string): void {
    this.ditaDraft = dita;
    this.save({ dita_content: dita }, 'Previous version restored');
  }

  isDone(issue: JobIssue): boolean {
    return /done|closed|released|resolved/i.test(issue.status || '');
  }

  isWarning(entry: ItemHistoryEntry): boolean {
    return ['jira_changed', 'flagged', 'issue_removed'].includes(entry.event_type);
  }

  historyGlyph(entry: ItemHistoryEntry): string {
    const glyphs: Record<string, string> = {
      created: '+', jira_changed: '!', regenerated: '↻', content_edited: '✎', status_changed: '◉',
      moved: '→', flagged: '⚑', issue_removed: '!', notes_edited: '≡',
    };
    return glyphs[entry.event_type] || '·';
  }

  actorLabel(entry: ItemHistoryEntry): string {
    return entry.actor === 'agent' ? 'Agent (chat)' : entry.actor === 'user' ? 'You' : 'Pipeline';
  }

  changesOf(entry: ItemHistoryEntry): any[] {
    const changes = entry.details?.['changes'] || {};
    return Object.keys(changes).map(key => ({ key, ...changes[key] }));
  }

  fmt(value: any): string {
    if (value === null || value === undefined || value === '') return '—';
    return Array.isArray(value) ? value.join(', ') : String(value);
  }
}
