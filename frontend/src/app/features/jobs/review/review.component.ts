import { Component, OnInit, inject, ChangeDetectionStrategy } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HopAccountService } from '@heretto/hop-ui';
import { ItemComment, Job, JobsService, ReleaseNoteItem, ReleaseNoteItemDetail } from '../../../core/services/jobs.service';

/** The notes of one group, as the sidebar lists them. */
interface ReviewGroup {
  name: string;
  notes: ReleaseNoteItem[];
}

/**
 * Reading view for everyone who is not the writer.
 *
 * Deliberately a plain route, not a tokenized share link: access is "signed in and in this
 * organization", which the API enforces on every call. The link in Share for review is just
 * this URL, so handing it to someone outside the organization gets them a login page, not
 * the notes.
 */
@Component({
  selector: 'app-review',
  standalone: true,
  imports: [
    DatePipe, RouterLink, FormsModule, MatButtonModule, MatIconModule, MatTooltipModule,
    MatProgressSpinnerModule
  ],
  template: `
    <div class="review">
      @if (loading) {
        <div class="loading"><mat-spinner></mat-spinner><p>Opening the review…</p></div>
      } @else if (job) {
        <header class="rv-header">
          <span class="rv-kicker">Review</span>
          <h1>{{ job.title || job.output_filename || 'Release notes' }}</h1>
          <span class="spacer"></span>
          <span class="muted">Reviewing as {{ viewerEmail }}</span>
          <a mat-stroked-button [routerLink]="['/releases', job.id, 'workspace']">
            <mat-icon>edit_note</mat-icon> Workspace
          </a>
        </header>

        <div class="rv-body">
          <aside class="rv-list">
            <div class="rv-list-head">
              <div class="rv-count">{{ items.length }} notes</div>
              <div class="muted">{{ assignedText }}</div>
              <div class="rv-filters">
                <button [class.on]="filter === 'mine'" (click)="filter = 'mine'">For me ({{ mineCount }})</button>
                <button [class.on]="filter === 'all'" (click)="filter = 'all'">All notes</button>
              </div>
            </div>

            <div class="rv-groups">
              @for (group of groups; track group.name) {
                <div class="rv-group">
                  <div class="rv-group-name">{{ group.name }}</div>
                  @for (note of group.notes; track note.id) {
                    <button class="rv-note" [class.on]="note.id === selectedId" (click)="select(note.id)">
                      <span class="rv-dot" [class.needs]="needsMe(note)" [class.done]="note.reviewed"
                            [matTooltip]="indicatorTitle(note)"></span>
                      <span class="rv-note-text">
                        <span class="rv-note-title">
                          {{ note.title }}
                          @if (note.status === 'approved') {
                            <mat-icon class="rv-approved-mark" [matTooltip]="approvalText(note)">verified</mat-icon>
                          }
                        </span>
                        <span class="muted">{{ noteMeta(note) }}</span>
                      </span>
                    </button>
                  }
                </div>
              } @empty {
                <p class="rv-empty muted">
                  {{ filter === 'mine' ? 'Nothing is assigned to you in this release.' : 'This release has no notes yet.' }}
                </p>
              }
            </div>
          </aside>

          <main class="rv-main">
            @if (selected) {
              <article class="rv-note-view">
                <div class="rv-note-head">
                  <span class="rv-group-chip">{{ selected.group_name || 'Other changes' }}</span>
                  <span class="rv-assign" [class.mine]="isMine(selected)" [class.done]="selected.reviewed">
                    {{ assignLabel(selected) }}
                  </span>
                  @if (selected.status === 'approved') {
                    <span class="rv-assign done">Approved</span>
                  }
                </div>
                <h2>{{ selected.title }}</h2>
                <p class="rv-summary">{{ selected.summary }}</p>

                <div class="rv-review-actions">
                  @if (selected.status === 'approved') {
                    <span class="rv-approved">
                      <mat-icon class="inline-icon">verified</mat-icon>
                      {{ approvalText(selected) }}
                    </span>
                    <button mat-button (click)="setApproved(false)" [disabled]="saving">Undo approval</button>
                  } @else {
                    <button mat-flat-button color="primary" (click)="setApproved(true)" [disabled]="saving">
                      <mat-icon>verified</mat-icon> Approve
                    </button>
                    <span class="muted">Says this note is ready to publish.</span>
                  }
                </div>

                <div class="rv-review-actions rv-reviewed-row">
                  @if (selected.reviewed) {
                    <span class="rv-reviewed"><mat-icon class="inline-icon">check</mat-icon> Reviewed</span>
                    @if (isMine(selected)) {
                      <button mat-button (click)="setReviewed(false)" [disabled]="saving">Undo</button>
                    }
                  } @else if (isMine(selected)) {
                    <button mat-stroked-button (click)="setReviewed(true)" [disabled]="saving">
                      Mark as reviewed
                    </button>
                    <span class="muted">Tells the writer you are done reading this note.</span>
                  }
                </div>

                <h3>Comments ({{ selected.comments.length }})</h3>
                @for (comment of selected.comments; track comment.id) {
                  <div class="rv-comment" [class.resolved]="comment.resolved">
                    <span class="avatar">{{ initialsOf(comment.user_email) }}</span>
                    <div class="rv-comment-body">
                      <div class="rv-comment-head">
                        <span class="rv-comment-name">{{ comment.user_email || 'Someone' }}</span>
                        <span class="muted">{{ comment.created_at | date:'short' }}</span>
                        @if (comment.resolved) {
                          <span class="resolved-tag"><mat-icon class="inline-icon">check</mat-icon> Resolved</span>
                        }
                        <span class="spacer"></span>
                        <button mat-button class="resolve-button" (click)="setResolved(comment, !comment.resolved)"
                                [disabled]="saving">
                          {{ comment.resolved ? 'Reopen' : 'Resolve' }}
                        </button>
                      </div>
                      <div class="rv-comment-text">{{ comment.body }}</div>
                    </div>
                  </div>
                } @empty {
                  <p class="muted">No comments yet.</p>
                }

                <div class="rv-compose">
                  <textarea [(ngModel)]="commentDraft" rows="2" placeholder="Leave a comment…"
                            [disabled]="saving"></textarea>
                  <div class="rv-compose-actions">
                    <span class="muted">Commenting as {{ viewerEmail }}</span>
                    <button mat-flat-button color="primary" (click)="addComment()"
                            [disabled]="!commentDraft.trim() || saving">Comment</button>
                  </div>
                </div>
              </article>
            } @else {
              <div class="rv-placeholder muted">Pick a note to read it and leave comments.</div>
            }
          </main>
        </div>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    /* Standalone — this view owns the whole window, with no shell chrome above it. */
    :host { display: block; height: 100vh; }
    .review { display: flex; flex-direction: column; height: 100%; background: var(--bg-primary); }
    .loading { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 80px; }
    .rv-header { display: flex; align-items: center; gap: 12px; padding: 12px 20px;
      border-bottom: 1px solid var(--border-default); flex-shrink: 0; }
    .rv-kicker { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
      color: var(--text-tertiary); }
    .rv-header h1 { margin: 0; font-size: 16px; font-weight: 600; }
    .spacer { flex: 1; }
    .muted { color: var(--text-tertiary); font-size: 12px; }
    .inline-icon { font-size: 14px; width: 14px; height: 14px; vertical-align: middle; }

    .rv-body { flex: 1; min-height: 0; display: grid; grid-template-columns: 320px 1fr; }
    .rv-list { border-right: 1px solid var(--border-default); display: flex; flex-direction: column; min-height: 0; }
    .rv-list-head { padding: 14px 16px; border-bottom: 1px solid var(--border-light); flex-shrink: 0; }
    .rv-count { font-size: 15px; font-weight: 600; }
    .rv-filters { display: inline-flex; margin-top: 10px; border: 1px solid var(--border-default);
      border-radius: 6px; overflow: hidden; }
    .rv-filters button { font: inherit; font-size: 13px; padding: 6px 12px; border: none;
      background: transparent; color: var(--text-secondary); cursor: pointer; }
    .rv-filters button + button { border-left: 1px solid var(--border-default); }
    .rv-filters button.on { background: var(--color-primary); color: var(--color-primary-contrast, #fff); }
    .rv-groups { flex: 1; min-height: 0; overflow-y: auto; padding: 8px 0 16px; }
    .rv-group-name { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
      color: var(--text-tertiary); padding: 10px 16px 4px; }
    .rv-note { display: flex; align-items: flex-start; gap: 10px; width: 100%; text-align: left;
      padding: 8px 16px; border: none; background: none; font: inherit; color: inherit; cursor: pointer; }
    .rv-note:hover { background: var(--bg-secondary); }
    .rv-note.on { background: var(--color-primary-bg); }
    .rv-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; flex-shrink: 0;
      background: var(--border-strong, var(--border-default)); }
    .rv-dot.needs { background: var(--color-primary); }
    .rv-dot.done { background: var(--color-success, var(--color-success-text)); }
    .rv-note-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .rv-note-title { font-size: 13px; line-height: 1.4; }
    .rv-empty { padding: 20px 16px; }

    .rv-main { min-height: 0; overflow-y: auto; }
    .rv-note-view { max-width: 720px; margin: 0 auto; padding: 28px 24px 60px; }
    .rv-note-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
    .rv-group-chip { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
      color: var(--text-tertiary); }
    .rv-assign { font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 999px;
      background: var(--bg-secondary); color: var(--text-secondary); }
    .rv-assign.mine { background: var(--color-primary-bg); color: var(--color-primary-text); }
    .rv-assign.done { background: var(--color-success-bg); color: var(--color-success-text); }
    .rv-note-view h2 { margin: 0 0 10px; font-size: 22px; line-height: 1.25; }
    .rv-summary { margin: 0 0 18px; font-size: 15px; line-height: 1.6; color: var(--text-secondary); }
    .rv-review-actions { display: flex; align-items: center; gap: 10px; padding-bottom: 18px;
      border-bottom: 1px solid var(--border-light); }
    .rv-reviewed { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 600;
      color: var(--color-success-text); }
    .rv-reviewed-row { border-bottom: none; padding-bottom: 0; padding-top: 10px; }
    .rv-approved { display: inline-flex; align-items: center; gap: 5px; font-size: 13px; font-weight: 600;
      color: var(--color-success-text); }
    .rv-approved-mark { font-size: 14px; width: 14px; height: 14px; vertical-align: middle;
      color: var(--color-success-text); margin-left: 4px; }
    .rv-note-view h3 { margin: 20px 0 10px; font-size: 13px; font-weight: 600; }
    .rv-comment { display: flex; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border-light); }
    .rv-comment.resolved .rv-comment-text, .rv-comment.resolved .rv-comment-name { color: var(--text-tertiary); }
    .rv-comment.resolved .avatar { opacity: 0.6; }
    .resolved-tag { display: inline-flex; align-items: center; gap: 3px; font-size: 11px; font-weight: 600;
      padding: 2px 8px; border-radius: 999px; background: var(--color-success-bg); color: var(--color-success-text); }
    .resolve-button { min-width: 0; }
    .avatar { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px;
      border-radius: 50%; background: var(--bg-secondary); font-size: 11px; font-weight: 600; flex-shrink: 0; }
    .rv-comment-body { flex: 1; min-width: 0; }
    .rv-comment-head { display: flex; gap: 8px; align-items: baseline; }
    .rv-comment-name { font-size: 13px; font-weight: 600; }
    .rv-comment-text { font-size: 14px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
    .rv-compose { margin-top: 16px; border: 1px solid var(--border-default); border-radius: 8px; padding: 10px; }
    .rv-compose:focus-within { border-color: var(--color-primary); }
    .rv-compose textarea { width: 100%; box-sizing: border-box; resize: vertical; border: none; outline: none;
      font: inherit; font-size: 14px; background: transparent; color: var(--text-primary); }
    .rv-compose-actions { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 6px; }
    .rv-placeholder { display: flex; align-items: center; justify-content: center; height: 100%; font-size: 14px; }
    @media (max-width: 1024px) { :host { height: auto; } .review { height: auto; } .rv-body { grid-template-columns: 1fr; } }
  `]
})
export class ReviewComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private jobsService = inject(JobsService);
  private snackBar = inject(MatSnackBar);
  private account = inject(HopAccountService);

  job: Job | null = null;
  items: ReleaseNoteItem[] = [];
  selected: ReleaseNoteItemDetail | null = null;
  selectedId: string | null = null;
  loading = true;
  saving = false;
  filter: 'mine' | 'all' = 'mine';
  commentDraft = '';
  viewerId = '';
  viewerEmail = '';

  ngOnInit(): void {
    const jobId = this.route.snapshot.paramMap.get('id');
    if (!jobId) { this.router.navigate(['/releases']); return; }

    // Who is reading decides which notes are "mine", so settle that before the list loads.
    this.account.getAccountInfo().subscribe({
      next: info => {
        this.viewerId = info.id;
        this.viewerEmail = info.email;
        this.loadJob(jobId);
      },
      error: () => this.loadJob(jobId)
    });
  }

  private loadJob(jobId: string): void {
    this.jobsService.getJob(jobId).subscribe({
      next: job => {
        this.job = job;
        this.loadItems();
      },
      error: () => {
        this.loading = false;
        this.snackBar.open('Could not open that release', 'Close', { duration: 4000 });
        this.router.navigate(['/releases']);
      }
    });
  }

  private loadItems(): void {
    this.jobsService.getItems(this.job!.id).subscribe({
      next: items => {
        this.items = items;
        // Open on something: whatever is assigned to this person, else the first note.
        if (!this.mineCount) this.filter = 'all';
        const first = this.visibleItems[0];
        if (first) this.select(first.id);
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.snackBar.open('Could not load the notes', 'Close', { duration: 4000 });
      }
    });
  }

  get visibleItems(): ReleaseNoteItem[] {
    return this.filter === 'mine' ? this.items.filter(item => this.isMine(item)) : this.items;
  }

  get groups(): ReviewGroup[] {
    const groups: ReviewGroup[] = [];
    for (const item of this.visibleItems) {
      const name = item.group_name || 'Other changes';
      const group = groups.find(g => g.name === name);
      if (group) group.notes.push(item); else groups.push({ name, notes: [item] });
    }
    return groups;
  }

  get mineCount(): number {
    return this.items.filter(item => this.isMine(item)).length;
  }

  get assignedText(): string {
    const mine = this.items.filter(item => this.isMine(item));
    if (!mine.length) return 'None assigned to you';
    const done = mine.filter(item => item.reviewed).length;
    return `${done} of ${mine.length} assigned to you reviewed`;
  }

  isMine(item: ReleaseNoteItem): boolean {
    return !!this.viewerId && item.reviewer_id === this.viewerId;
  }

  needsMe(item: ReleaseNoteItem): boolean {
    return this.isMine(item) && !item.reviewed;
  }

  indicatorTitle(item: ReleaseNoteItem): string {
    if (item.reviewed) return 'Reviewed';
    if (this.isMine(item)) return 'Assigned to you';
    return item.reviewer_email ? `Reviewer: ${item.reviewer_email}` : 'No reviewer';
  }

  noteMeta(item: ReleaseNoteItem): string {
    const bits: string[] = [];
    if (item.comment_count) bits.push(`${item.comment_count} comment${item.comment_count === 1 ? '' : 's'}`);
    if (!this.isMine(item) && item.reviewer_email) bits.push(item.reviewer_email);
    return bits.join(' · ');
  }

  assignLabel(item: ReleaseNoteItem): string {
    if (this.isMine(item)) return item.reviewed ? 'Reviewed by you' : 'Assigned to you';
    if (item.reviewer_email) return `Reviewer: ${item.reviewer_email}`;
    return 'No reviewer';
  }

  setResolved(comment: ItemComment, resolved: boolean): void {
    if (!this.selected || this.saving) return;
    this.saving = true;
    this.jobsService.resolveComment(this.job!.id, this.selected.id, comment.id, resolved).subscribe({
      next: updated => {
        this.saving = false;
        // Patch in place: reloading the note would discard an unsent comment draft.
        if (this.selected) {
          this.selected = {
            ...this.selected,
            comments: this.selected.comments.map(c => c.id === updated.id ? updated : c)
          };
        }
      },
      error: () => {
        this.saving = false;
        this.snackBar.open('Could not update the comment', 'Close', { duration: 3000 });
      }
    });
  }

  initialsOf(email: string | null | undefined): string {
    const parts = (email || '?').split('@')[0].split(/[._-]+/).filter(Boolean);
    return ((parts[0]?.[0] || '?') + (parts[1]?.[0] || '')).toUpperCase();
  }

  select(itemId: string): void {
    this.selectedId = itemId;
    this.commentDraft = '';
    this.jobsService.getItem(this.job!.id, itemId).subscribe({
      next: item => this.selected = item,
      error: () => this.snackBar.open('Could not load that note', 'Close', { duration: 3000 })
    });
  }

  /** "Approved by someone@example.com on 14 Oct" — or just "Approved" for older notes. */
  approvalText(item: ReleaseNoteItem): string {
    if (item.status !== 'approved') return '';
    if (!item.approved_by_email) return 'Approved';
    const when = item.approved_at ? new Date(item.approved_at).toLocaleString() : '';
    return when
      ? `Approved by ${item.approved_by_email} on ${when}`
      : `Approved by ${item.approved_by_email}`;
  }

  setApproved(approved: boolean): void {
    if (!this.selected || this.saving) return;
    this.saving = true;
    // Back to review, not draft: the note has been written and read, it is the sign-off
    // that was withdrawn.
    const status = approved ? 'approved' : 'review';
    this.jobsService.updateItem(this.job!.id, this.selected.id, { status }).subscribe({
      next: item => {
        this.saving = false;
        this.applyUpdate(item);
      },
      error: error => {
        this.saving = false;
        this.snackBar.open(
          typeof error.error?.detail === 'string' ? error.error.detail : 'Could not save that',
          'Close', { duration: 5000 });
      }
    });
  }

  setReviewed(reviewed: boolean): void {
    if (!this.selected || this.saving) return;
    this.saving = true;
    this.jobsService.updateItem(this.job!.id, this.selected.id, { reviewed }).subscribe({
      next: item => {
        this.saving = false;
        this.applyUpdate(item);
      },
      error: () => {
        this.saving = false;
        this.snackBar.open('Could not save that', 'Close', { duration: 3000 });
      }
    });
  }

  addComment(): void {
    const body = this.commentDraft.trim();
    if (!body || !this.selected || this.saving) return;
    this.saving = true;
    this.jobsService.addComment(this.job!.id, this.selected.id, body).subscribe({
      next: () => {
        this.saving = false;
        this.commentDraft = '';
        this.select(this.selected!.id);
        this.bumpCommentCount();
      },
      error: () => {
        this.saving = false;
        this.snackBar.open('Could not add the comment', 'Close', { duration: 3000 });
      }
    });
  }

  private applyUpdate(item: ReleaseNoteItemDetail): void {
    this.selected = item;
    this.items = this.items.map(existing => existing.id === item.id ? { ...existing, ...item } : existing);
  }

  private bumpCommentCount(): void {
    const id = this.selected?.id;
    this.items = this.items.map(item =>
      item.id === id ? { ...item, comment_count: item.comment_count + 1 } : item);
  }
}
