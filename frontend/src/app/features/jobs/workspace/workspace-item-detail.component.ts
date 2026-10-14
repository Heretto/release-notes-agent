import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges, inject, ChangeDetectionStrategy } from '@angular/core';
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
import {
  JobsService, ReleaseNoteItemDetail, ItemStatus, ITEM_STATUSES, ItemHistoryEntry, JobIssue
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
              @for (key of item.issue_keys; track key) { · {{ key }} }
              @if (item.user_edited) { · <mat-icon class="inline-icon" matTooltip="Edited by a person">edit</mat-icon> }
            </div>
          </div>
          <button mat-icon-button matTooltip="Back to chat" (click)="closed.emit()"><mat-icon>close</mat-icon></button>
        </div>

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

          <mat-tab label="Links ({{ item.references.length }})">
            <div class="tab-body">
              <p class="muted">Your own references for this note: a Slack thread, a design doc, a support case.</p>
              @for (reference of item.references; track reference.id) {
                <div class="reference-row">
                  <mat-icon>link</mat-icon>
                  <a [href]="reference.url" target="_blank" rel="noopener">{{ reference.label || reference.url }}</a>
                  <span class="spacer"></span>
                  <button mat-icon-button matTooltip="Remove" (click)="removeReference(reference.id)" [disabled]="saving">
                    <mat-icon>close</mat-icon>
                  </button>
                </div>
              }
              <form class="reference-form" (ngSubmit)="addReference()">
                <mat-form-field appearance="outline" subscriptSizing="dynamic" class="grow">
                  <mat-label>URL</mat-label>
                  <input matInput [(ngModel)]="referenceUrl" name="url" placeholder="https://…" [disabled]="saving">
                </mat-form-field>
                <mat-form-field appearance="outline" subscriptSizing="dynamic" class="grow">
                  <mat-label>Label</mat-label>
                  <input matInput [(ngModel)]="referenceLabel" name="label" placeholder="Slack thread" [disabled]="saving">
                </mat-form-field>
                <button mat-flat-button color="primary" type="submit" [disabled]="!referenceUrl.trim() || saving">Add</button>
              </form>
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
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    :host { display: block; height: 100%; }
    .detail { display: flex; flex-direction: column; height: 100%; min-height: 0; }
    .loading { display: flex; justify-content: center; padding: 40px; }
    .detail-head { display: flex; align-items: flex-start; gap: 8px; padding: 12px 16px 8px; }
    .title-block { flex: 1; min-width: 0; }
    .title-block h3 { margin: 0 0 2px; font-size: 16px; cursor: text; line-height: 1.3; }
    .title-input { width: 100%; font: inherit; font-size: 16px; font-weight: 600; padding: 4px 8px; border: 1px solid var(--border-focus); border-radius: 6px; }
    .title-actions { display: flex; justify-content: flex-end; gap: 4px; margin-top: 4px; }
    .muted { color: var(--text-tertiary); font-size: 12px; }
    .inline-icon { font-size: 14px; width: 14px; height: 14px; vertical-align: middle; }
    .status-row { display: flex; gap: 8px; padding: 4px 16px 8px; }
    .status-field { width: 150px; }
    .group-field { flex: 1; }
    .attention-banner { display: flex; align-items: center; gap: 10px; margin: 0 16px 8px; padding: 10px 12px; background: var(--color-warning-bg); color: var(--color-warning-text); border-radius: 8px; font-size: 13px; }
    .attention-banner mat-icon { color: var(--color-warning); }
    .attention-text { flex: 1; }
    .detail-tabs { flex: 1; min-height: 0; display: flex; flex-direction: column; }
    .detail-tabs ::ng-deep .mat-mdc-tab-body-wrapper { flex: 1; min-height: 0; }
    .detail-tabs ::ng-deep .mat-mdc-tab-body-content { overflow-y: auto; }
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
    .reference-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--border-light); }
    .reference-row a { word-break: break-all; }
    .reference-form { display: flex; gap: 8px; align-items: center; margin-top: 12px; flex-wrap: wrap; }
    .reference-form .grow { flex: 1; min-width: 140px; }
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

  editingTitle = false;
  titleDraft = '';
  groupDraft = '';
  ditaDraft = '';
  ditaErrors: string[] = [];
  referenceUrl = '';
  referenceLabel = '';

  get ditaDirty(): boolean {
    return !!this.item && this.ditaDraft.trim() !== (this.item.dita_content || '').trim();
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

  addReference(): void {
    const url = this.referenceUrl.trim();
    if (!url || !this.item) return;
    this.saving = true;
    this.jobsService.addReference(this.jobId, this.item.id, { url, label: this.referenceLabel.trim() || undefined }).subscribe({
      next: () => {
        this.saving = false;
        this.referenceUrl = '';
        this.referenceLabel = '';
        this.load();
        this.updated.emit(this.item!);
      },
      error: (error) => {
        this.saving = false;
        this.snackBar.open(error.error?.detail || 'Failed to add the link', 'Close', { duration: 4000 });
      }
    });
  }

  removeReference(referenceId: string): void {
    if (!this.item) return;
    this.saving = true;
    this.jobsService.removeReference(this.jobId, this.item.id, referenceId).subscribe({
      next: () => {
        this.saving = false;
        this.load();
        this.updated.emit(this.item!);
      },
      error: () => {
        this.saving = false;
        this.snackBar.open('Failed to remove the link', 'Close', { duration: 3000 });
      }
    });
  }

  isDone(issue: JobIssue): boolean {
    return /done|closed|released|resolved/i.test(issue.status || '');
  }

  historyIcon(entry: ItemHistoryEntry): string {
    const icons: Record<string, string> = {
      created: 'add_circle', jira_changed: 'sync_problem', regenerated: 'auto_fix_high', content_edited: 'edit',
      status_changed: 'flag_circle', moved: 'low_priority', flagged: 'flag', issue_removed: 'link_off',
      reference_added: 'add_link', reference_removed: 'link_off',
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
