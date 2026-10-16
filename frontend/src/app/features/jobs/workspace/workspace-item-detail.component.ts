import { Component, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges, inject, ChangeDetectionStrategy } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HopOrganizationService, OrganizationMember } from '@heretto/hop-ui';
import {
  JobsService, ReleaseNoteItemDetail, ItemComment, ItemStatus, ITEM_STATUSES, ItemHistoryEntry, JobIssue
} from '../../../core/services/jobs.service';

@Component({
  selector: 'app-workspace-item-detail',
  standalone: true,
  imports: [
    DatePipe, FormsModule, MatButtonModule, MatIconModule, MatTabsModule, MatSelectModule,
    MatFormFieldModule, MatInputModule, MatTooltipModule, MatProgressSpinnerModule, MatExpansionModule
  ],
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
                <button mat-button (click)="editingTitle = false">Cancel</button>
                <button mat-flat-button color="primary" (click)="saveTitle()" [disabled]="!titleDraft.trim() || saving">Save</button>
              </div>
            } @else {
              <h3 (click)="startTitleEdit()" matTooltip="Click to rename">{{ item.title }}</h3>
            }
            <div class="muted">
              {{ item.group_name || 'No group' }}
              @if (item.issues.length) {
                ·
                @for (issue of item.issues; track issue.id; let last = $last) {
                  <a [href]="issue.url" target="_blank" rel="noopener" class="issue-link">{{ issue.issue_key }}</a>@if (!last) {, }
                }
              }
              @if (item.user_edited) { · <mat-icon class="inline-icon" matTooltip="Edited by a person">edit</mat-icon> }
            </div>
          </div>
          <button mat-icon-button matTooltip="Back to chat" (click)="closed.emit()"><mat-icon>close</mat-icon></button>
        </div>

        <!-- Everything below the pinned header scrolls as one unit: the fields, the notes
             and the tab content move together rather than each tab scrolling on its own. -->
        <div class="detail-body">
        <div class="status-row">
          <mat-form-field appearance="outline" class="status-field" subscriptSizing="dynamic">
            <mat-label>Status</mat-label>
            <mat-select [value]="item.status" (selectionChange)="setStatus($event.value)" [disabled]="saving">
              @for (status of statuses; track status.value) {
                <mat-option [value]="status.value">{{ status.label }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" class="group-field" subscriptSizing="dynamic">
            <mat-label>Group</mat-label>
            <input matInput [(ngModel)]="groupDraft" (blur)="saveGroup()" (keydown.enter)="saveGroup()" [disabled]="saving" list="groups">
            <datalist id="groups">
              @for (group of groups; track group) { <option [value]="group"></option> }
            </datalist>
          </mat-form-field>
        </div>

        <div class="status-row">
          <mat-form-field appearance="outline" class="reviewer-field" subscriptSizing="dynamic">
            <mat-label>Reviewer</mat-label>
            <mat-select [value]="item.reviewer_id || null" (selectionChange)="setReviewer($event.value)" [disabled]="saving">
              <mat-option [value]="null">No reviewer</mat-option>
              @for (member of members; track member.user_id) {
                <mat-option [value]="member.user_id">{{ member.user_email }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          @if (item.reviewed) {
            <span class="reviewed-chip"><mat-icon class="inline-icon">check</mat-icon> Reviewed</span>
          }
        </div>

        <div class="notes-block">
          <span class="notes-label">Notes</span>
          @if (editingNotes) {
            <textarea class="notes-editor" [(ngModel)]="notesDraft" rows="5" [disabled]="saving"
                      placeholder="Context, open questions, links to a Slack thread or design doc…"></textarea>
            <div class="notes-actions">
              <button mat-button (click)="cancelNotes()" [disabled]="saving">Cancel</button>
              <button mat-flat-button color="primary" (click)="saveNotes()" [disabled]="saving">Save</button>
            </div>
          } @else if (item.notes) {
            <p class="notes-body">
              @for (part of noteParts; track $index) {
                @if (part.isLink) {
                  <a [href]="part.text" target="_blank" rel="noopener">{{ part.text }}</a>
                } @else {
                  <span>{{ part.text }}</span>
                }
              }
            </p>
            <div class="notes-actions">
              <button mat-button (click)="startNotesEdit()" [disabled]="disabled || saving">Edit notes</button>
            </div>
          } @else {
            <button class="notes-empty" (click)="startNotesEdit()" [disabled]="disabled || saving">
              Add notes — context, open questions, links…
            </button>
          }
        </div>

        @if (item.needs_attention) {
          <div class="attention-banner">
            <mat-icon>flag</mat-icon>
            <div class="attention-text">
              <strong>Needs attention</strong>
              <div>{{ item.attention_reason }}</div>
            </div>
            <button mat-button (click)="clearAttention()" [disabled]="saving">Clear</button>
          </div>
        }

        <mat-tab-group class="detail-tabs" animationDuration="0ms">
          <mat-tab label="Jira">
            <div class="tab-body">
              <p class="summary">{{ item.summary }}</p>
              @if (item.issues.length === 0) {
                <p class="muted">This note is not linked to a Jira issue.</p>
              }
              @for (issue of item.issues; track issue.id) {
                <div class="issue-card" [class.dropped]="!issue.in_query">
                  <div class="issue-head">
                    <a [href]="issue.url" target="_blank" rel="noopener" class="issue-key">
                      {{ issue.issue_key }} <mat-icon class="inline-icon">open_in_new</mat-icon>
                    </a>
                    <span class="hop-status-chip">{{ issue.issue_type }}</span>
                    <span class="hop-status-chip" [class.hop-status-chip-completed]="isDone(issue)">{{ issue.status }}</span>
                    @if (issue.item_ids.length > 1) {
                      <span class="hop-status-chip hop-status-chip-pending" matTooltip="This issue feeds several release notes">{{ issue.item_ids.length }} notes</span>
                    }
                    @if (!issue.in_query) {
                      <span class="hop-status-chip hop-status-chip-failed">Left the query</span>
                    }
                  </div>
                  <div class="issue-summary">{{ issue.summary }}</div>
                  @if (issue.description) {
                    <mat-expansion-panel class="flat-panel">
                      <mat-expansion-panel-header><mat-panel-title>Description</mat-panel-title></mat-expansion-panel-header>
                      <pre class="issue-text">{{ issue.description }}</pre>
                    </mat-expansion-panel>
                  }
                  @if (issue.comments.length) {
                    <mat-expansion-panel class="flat-panel">
                      <mat-expansion-panel-header><mat-panel-title>Comments ({{ issue.comments.length }})</mat-panel-title></mat-expansion-panel-header>
                      @for (comment of issue.comments; track $index) {
                        <pre class="issue-text comment">{{ comment }}</pre>
                      }
                    </mat-expansion-panel>
                  }
                  <div class="issue-meta muted">
                    @if (issue.priority) { {{ issue.priority }} · }
                    @if (issue.assignee) { {{ issue.assignee }} · }
                    @if (issue.components.length) { {{ issue.components.join(', ') }} · }
                    @if (issue.fix_versions.length) { {{ issue.fix_versions.join(', ') }} · }
                    @if (issue.jira_updated) { updated {{ issue.jira_updated | date:'short' }} }
                  </div>
                  @if (issue.relevance_reason) {
                    <div class="muted reason"><mat-icon class="inline-icon">psychology</mat-icon> {{ issue.relevance_reason }}</div>
                  }
                </div>
              }
            </div>
          </mat-tab>

          <mat-tab label="DITA">
            <div class="tab-body">
              <textarea class="dita-editor" [(ngModel)]="ditaDraft" spellcheck="false" [disabled]="saving"></textarea>
              @if (ditaErrors.length) {
                <ul class="errors">
                  @for (error of ditaErrors; track $index) { <li>{{ error }}</li> }
                </ul>
              }
              <div class="editor-actions">
                <span class="muted">One <code>&lt;div outputclass="release-note"&gt;</code>; validated against DITA 1.3 on save</span>
                <span class="spacer"></span>
                <button mat-button (click)="resetDita()" [disabled]="!ditaDirty || saving">Reset</button>
                <button mat-flat-button color="primary" (click)="saveDita()" [disabled]="!ditaDirty || saving">Save</button>
              </div>
            </div>
          </mat-tab>

          <mat-tab label="Comments ({{ item.comments.length }})">
            <div class="tab-body">
              @for (comment of item.comments; track comment.id) {
                <div class="comment-row" [class.resolved]="comment.resolved">
                  <span class="avatar">{{ initialsOf(comment.user_email) }}</span>
                  <div class="comment-body">
                    <div class="comment-head">
                      <span class="comment-name">{{ comment.user_email || 'Someone' }}</span>
                      <span class="muted">{{ comment.created_at | date:'short' }}</span>
                      @if (comment.resolved) {
                        <span class="resolved-tag"><mat-icon class="inline-icon">check</mat-icon> Resolved</span>
                      }
                    </div>
                    <div class="comment-text">{{ comment.body }}</div>
                    <div class="comment-row-actions">
                      @if (!comment.resolved) {
                        <button mat-button (click)="askAgentToFix(comment)" [disabled]="disabled || saving"
                                matTooltip="Send this comment to the agent in the chat">
                          <mat-icon>auto_fix_high</mat-icon> Ask the agent
                        </button>
                        <button mat-button (click)="setResolved(comment, true)" [disabled]="saving">Resolve</button>
                      } @else {
                        <span class="muted">
                          @if (comment.resolved_by_email) { by {{ comment.resolved_by_email }} }
                        </span>
                        <button mat-button (click)="setResolved(comment, false)" [disabled]="saving">Reopen</button>
                      }
                    </div>
                  </div>
                </div>
              } @empty {
                <p class="muted">No comments yet.</p>
              }
              <div class="comment-compose">
                <textarea [(ngModel)]="commentDraft" rows="2" placeholder="Leave a comment…"
                          [disabled]="saving"></textarea>
                <div class="comment-actions">
                  <button mat-flat-button color="primary" (click)="addComment()"
                          [disabled]="!commentDraft.trim() || saving">Comment</button>
                </div>
              </div>
            </div>
          </mat-tab>

          <mat-tab label="History ({{ item.history.length }})">
            <div class="tab-body">
              <ol class="timeline">
                @for (entry of item.history; track entry.id) {
                  <li [class]="'event event-' + entry.event_type">
                    <span class="event-icon"><mat-icon>{{ historyIcon(entry) }}</mat-icon></span>
                    <div class="event-body">
                      <div class="event-summary">{{ entry.summary }}</div>
                      <div class="muted">{{ actorLabel(entry) }} · {{ entry.created_at | date:'medium' }}</div>
                      @if (entry.details?.['changes']) {
                        <ul class="diff">
                          @for (change of changesOf(entry); track change.label) {
                            <li>
                              <strong>{{ change.label }}</strong>
                              @if (change.added) {
                                : {{ change.added.length }} new comment(s)
                                @for (comment of change.added; track $index) { <pre class="issue-text comment">{{ comment }}</pre> }
                              } @else {
                                <div class="diff-pair">
                                  <span class="from">{{ fmt(change.from) }}</span>
                                  <mat-icon class="inline-icon">arrow_forward</mat-icon>
                                  <span class="to">{{ fmt(change.to) }}</span>
                                </div>
                              }
                            </li>
                          }
                        </ul>
                      }
                      @if (entry.details?.['previous_dita']) {
                        <mat-expansion-panel class="flat-panel">
                          <mat-expansion-panel-header><mat-panel-title>Previous content</mat-panel-title></mat-expansion-panel-header>
                          <pre class="issue-text">{{ entry.details!['previous_dita'] }}</pre>
                          <button mat-button (click)="restorePrevious(entry.details!['previous_dita'])" [disabled]="saving">Restore this version</button>
                        </mat-expansion-panel>
                      }
                    </div>
                  </li>
                }
              </ol>
            </div>
          </mat-tab>
        </mat-tab-group>
        </div>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    :host { display: block; height: 100%; }
    .detail { display: flex; flex-direction: column; height: 100%; min-height: 0; }
    .loading { display: flex; justify-content: center; padding: 40px; }
    /* Pinned: the title and the Jira keys stay put while the body scrolls under them. */
    .detail-head { display: flex; align-items: flex-start; gap: 8px; padding: 12px 16px 8px;
      flex-shrink: 0; border-bottom: 1px solid var(--border-subtle); background: var(--bg-primary); }
    .detail-body { flex: 1; min-height: 0; overflow-y: auto; }
    .issue-link { color: inherit; text-decoration: underline; }
    .issue-link:hover { color: var(--color-primary); }
    .title-block { flex: 1; min-width: 0; }
    .title-block h3 { margin: 0 0 2px; font-size: 16px; cursor: text; line-height: 1.3; }
    .title-input { width: 100%; font: inherit; font-size: 16px; font-weight: 600; padding: 4px 8px; border: 1px solid var(--border-focus); border-radius: 6px; }
    .title-actions { display: flex; justify-content: flex-end; gap: 4px; margin-top: 4px; }
    .muted { color: var(--text-tertiary); font-size: 12px; }
    .inline-icon { font-size: 14px; width: 14px; height: 14px; vertical-align: middle; }
    .status-row { display: flex; gap: 8px; padding: 4px 16px 8px; }
    .notes-block { padding: 0 16px 12px; display: flex; flex-direction: column; gap: 6px; }
    .notes-label { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
    .notes-editor { width: 100%; box-sizing: border-box; resize: vertical; padding: 8px 10px;
      border: 1px solid var(--border-default); border-radius: 4px; font: inherit; font-size: 13px; }
    .notes-editor:focus { outline: none; border-color: var(--color-primary); }
    .notes-body { margin: 0; font-size: 13px; line-height: 1.55; white-space: pre-wrap; word-break: break-word; }
    .notes-body a { word-break: break-all; }
    .notes-actions { display: flex; justify-content: flex-end; gap: 4px; }
    .notes-empty { align-self: flex-start; background: none; border: none; padding: 0; cursor: pointer;
      font: inherit; font-size: 13px; color: var(--text-tertiary); text-align: left; }
    .notes-empty:hover:not(:disabled) { color: var(--color-primary); }
    .notes-empty:disabled { cursor: default; }
    .status-field { width: 150px; }
    .reviewer-field { flex: 1; }
    .reviewed-chip { display: inline-flex; align-items: center; gap: 4px; align-self: center; font-size: 12px;
      font-weight: 600; padding: 4px 10px; border-radius: 999px;
      background: var(--color-success-bg); color: var(--color-success-text); }
    .comment-row { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
    .comment-row.resolved .comment-text, .comment-row.resolved .comment-name { color: var(--text-tertiary); }
    .comment-row.resolved .avatar { opacity: 0.6; }
    .resolved-tag { display: inline-flex; align-items: center; gap: 3px; font-size: 11px; font-weight: 600;
      padding: 2px 8px; border-radius: 999px; background: var(--color-success-bg); color: var(--color-success-text); }
    .comment-row-actions { display: flex; align-items: center; justify-content: flex-end; gap: 4px; margin-top: 2px; }
    .comment-row-actions .mat-mdc-button { min-width: 0; }
    .avatar { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px;
      border-radius: 50%; background: var(--bg-secondary); font-size: 11px; font-weight: 600; flex-shrink: 0; }
    .comment-body { flex: 1; min-width: 0; }
    .comment-head { display: flex; gap: 8px; align-items: baseline; }
    .comment-name { font-size: 13px; font-weight: 600; }
    .comment-text { font-size: 13px; line-height: 1.55; white-space: pre-wrap; word-break: break-word; }
    .comment-compose { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
    .comment-compose textarea { width: 100%; box-sizing: border-box; resize: vertical; padding: 8px 10px;
      border: 1px solid var(--border-default); border-radius: 4px; font: inherit; font-size: 13px; }
    .comment-compose textarea:focus { outline: none; border-color: var(--color-primary); }
    .comment-actions { display: flex; justify-content: flex-end; }
    .group-field { flex: 1; }
    .attention-banner { display: flex; align-items: center; gap: 10px; margin: 0 16px 8px; padding: 10px 12px; background: var(--color-warning-bg); color: var(--color-warning-text); border-radius: 8px; font-size: 13px; }
    .attention-banner mat-icon { color: var(--color-warning); }
    .attention-text { flex: 1; }
    .detail-tabs ::ng-deep .mat-mdc-tab-body-content { overflow: visible; }
    .tab-body { padding: 12px 16px 16px; font-size: 14px; }
    .summary { margin: 0 0 12px; color: var(--text-secondary); }
    .issue-card { border: 1px solid var(--border-default); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
    .issue-card.dropped { opacity: 0.7; }
    .issue-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
    .issue-key { font-family: var(--font-mono); font-size: 13px; font-weight: 500; display: inline-flex; align-items: center; gap: 2px; }
    .issue-summary { font-weight: 500; margin-bottom: 6px; }
    .issue-text { white-space: pre-wrap; word-break: break-word; font: inherit; font-size: 13px; margin: 0; color: var(--text-secondary); }
    .issue-text.comment { border-left: 2px solid var(--border-strong); padding-left: 8px; margin: 6px 0; }
    .issue-meta { margin-top: 6px; }
    .reason { margin-top: 4px; display: flex; gap: 4px; align-items: center; }
    .flat-panel { box-shadow: none !important; border: 1px solid var(--border-light); margin: 6px 0; }
    .flat-panel ::ng-deep .mat-expansion-panel-header { height: 36px; font-size: 13px; }
    .dita-editor { width: 100%; min-height: 320px; font-family: var(--font-mono); font-size: 12px; line-height: 1.5; border: 1px solid var(--border-strong); border-radius: 8px; padding: 10px; resize: vertical; background: var(--bg-primary); color: var(--text-primary); box-sizing: border-box; }
    .dita-editor:focus { outline: none; border-color: var(--border-focus); box-shadow: var(--focus-ring); }
    .errors { margin: 8px 0; padding: 8px 12px 8px 28px; background: var(--color-error-bg); color: var(--color-error-text); border-radius: 6px; font-size: 12px; }
    .editor-actions { display: flex; align-items: center; gap: 6px; margin-top: 8px; }
    .editor-actions code { font-family: var(--font-mono); }
    .spacer { flex: 1; }
    .timeline { list-style: none; margin: 0; padding: 0; }
    .event { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
    .event-icon { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 50%; background: var(--bg-secondary); flex-shrink: 0; }
    .event-icon mat-icon { font-size: 16px; width: 16px; height: 16px; color: var(--text-secondary); }
    .event-jira_changed .event-icon, .event-flagged .event-icon, .event-issue_removed .event-icon { background: var(--color-warning-bg); }
    .event-jira_changed .event-icon mat-icon, .event-flagged .event-icon mat-icon, .event-issue_removed .event-icon mat-icon { color: var(--color-warning-text); }
    .event-body { flex: 1; min-width: 0; }
    .event-summary { font-size: 13px; }
    .diff { margin: 6px 0 0; padding-left: 16px; font-size: 12px; }
    .diff-pair { display: flex; gap: 6px; align-items: baseline; flex-wrap: wrap; }
    .diff-pair .from { color: var(--color-error-text); text-decoration: line-through; }
    .diff-pair .to { color: var(--color-success-text); }
  `]
})
export class WorkspaceItemDetailComponent implements OnChanges, OnInit {
  private jobsService = inject(JobsService);
  private snackBar = inject(MatSnackBar);
  private organizationService = inject(HopOrganizationService);

  @Input({ required: true }) jobId!: string;
  @Input({ required: true }) itemId!: string;
  @Input() groups: string[] = [];
  @Input() disabled = false;
  @Output() updated = new EventEmitter<ReleaseNoteItemDetail>();
  @Output() closed = new EventEmitter<void>();
  /** A comment to put to the agent, sent by the workspace into the chat pane. */
  @Output() askAgent = new EventEmitter<string>();

  item: ReleaseNoteItemDetail | null = null;
  loading = true;
  saving = false;
  statuses = ITEM_STATUSES;

  editingTitle = false;
  titleDraft = '';
  groupDraft = '';
  ditaDraft = '';
  ditaErrors: string[] = [];
  editingNotes = false;
  notesDraft = '';
  commentDraft = '';
  members: OrganizationMember[] = [];

  get ditaDirty(): boolean {
    return !!this.item && this.ditaDraft.trim() !== (this.item.dita_content || '').trim();
  }

  /** The notes split into plain text and bare URLs, so URLs render as links. */
  get noteParts(): { text: string; isLink: boolean }[] {
    const notes = this.item?.notes || '';
    if (!notes) return [];
    return notes
      .split(/(https?:\/\/[^\s]+)/g)
      .filter(part => part !== '')
      .map(part => ({ text: part, isLink: /^https?:\/\//.test(part) }));
  }

  ngOnInit(): void {
    // Reviewers are the organization's members — review is for signed-in members only, so
    // there is no separate list of people to keep.
    this.organizationService.listMembers().subscribe({
      next: members => this.members = members,
      error: () => this.members = []
    });
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
    this.editingNotes = false;
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

  setReviewer(reviewerId: string | null): void {
    if ((reviewerId || null) !== (this.item?.reviewer_id || null)) {
      this.save({ reviewer_id: reviewerId }, reviewerId ? 'Reviewer assigned' : 'Reviewer cleared');
    }
  }

  addComment(): void {
    const body = this.commentDraft.trim();
    if (!body || !this.item || this.saving) return;
    this.saving = true;
    this.jobsService.addComment(this.jobId, this.item.id, body).subscribe({
      next: () => {
        this.saving = false;
        this.commentDraft = '';
        // Reload rather than push: the comment also lands in the note's history.
        this.load();
      },
      error: () => {
        this.saving = false;
        this.snackBar.open('Failed to add the comment', 'Close', { duration: 3000 });
      }
    });
  }

  setResolved(comment: ItemComment, resolved: boolean): void {
    if (!this.item || this.saving) return;
    this.saving = true;
    this.jobsService.resolveComment(this.jobId, this.item.id, comment.id, resolved).subscribe({
      next: updated => {
        this.saving = false;
        // Patch in place rather than reloading: the note itself has not changed, and a
        // reload would throw away an unsent comment draft.
        if (this.item) {
          this.item = {
            ...this.item,
            comments: this.item.comments.map(c => c.id === updated.id ? updated : c)
          };
        }
      },
      error: () => {
        this.saving = false;
        this.snackBar.open('Failed to update the comment', 'Close', { duration: 3000 });
      }
    });
  }

  /**
   * Hand a comment to the writer agent as an instruction. The workspace shows the chat and
   * sends it there, so what was asked and what the agent did stay in one transcript.
   */
  askAgentToFix(comment: ItemComment): void {
    if (!this.item) return;
    const who = comment.user_email || 'A reviewer';
    this.askAgent.emit(
      `${who} commented on the note “${this.item.title}”:\n\n` +
      `"${comment.body}"\n\n` +
      `Please update that note to address the comment.`
    );
  }

  /** Initials from an email, for the comment avatars. */
  initialsOf(email: string | null | undefined): string {
    const name = (email || '?').split('@')[0];
    const parts = name.split(/[._-]+/).filter(Boolean);
    return ((parts[0]?.[0] || '?') + (parts[1]?.[0] || '')).toUpperCase();
  }

  setStatus(status: ItemStatus): void {
    if (status !== this.item?.status) this.save({ status });
  }

  saveGroup(): void {
    const group = this.groupDraft.trim();
    if (group !== (this.item?.group_name || '')) this.save({ group_name: group });
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

  startNotesEdit(): void {
    if (this.disabled) return;
    this.notesDraft = this.item?.notes || '';
    this.editingNotes = true;
  }

  cancelNotes(): void {
    this.editingNotes = false;
    this.notesDraft = this.item?.notes || '';
  }

  saveNotes(): void {
    const notes = this.notesDraft.trim();
    if (!this.item || notes === (this.item.notes || '').trim()) {
      this.editingNotes = false;
      return;
    }
    this.save({ notes }, notes ? 'Notes saved' : 'Notes cleared');
  }

  isDone(issue: JobIssue): boolean {
    return /done|closed|released|resolved/i.test(issue.status || '');
  }

  historyIcon(entry: ItemHistoryEntry): string {
    const icons: Record<string, string> = {
      created: 'add_circle', jira_changed: 'sync_problem', regenerated: 'auto_fix_high', content_edited: 'edit',
      status_changed: 'flag_circle', moved: 'low_priority', flagged: 'flag', issue_removed: 'link_off',
      notes_edited: 'sticky_note_2', reviewer_assigned: 'person_add', reviewed: 'task_alt',
      comment_added: 'comment', comment_resolved: 'mark_chat_read',
    };
    return icons[entry.event_type] || 'history';
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
