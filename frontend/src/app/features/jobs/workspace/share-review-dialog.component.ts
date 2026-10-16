import { Component, Inject, ChangeDetectionStrategy } from '@angular/core';
import { Router } from '@angular/router';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ReleaseNoteItem } from '../../../core/services/jobs.service';

export interface ShareReviewDialogData {
  jobId: string;
  items: ReleaseNoteItem[];
}

/** One line of the dialog: a reviewer, or the catch-all for notes nobody is reading. */
interface ReviewerRow {
  initials: string;
  name: string;
  countText: string;
  unassigned: boolean;
}

@Component({
  selector: 'app-share-review-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule],
  template: `
    <h2 mat-dialog-title>Share for review</h2>

    <mat-dialog-content class="share-content">
      <p class="intro">
        Anyone signed in to this organization can open the link and read every note and comment.
        Assigned reviewers see which notes are theirs.
      </p>

      <span class="label">Reviewers</span>
      <div class="rows">
        @for (row of rows; track row.name) {
          <div class="row" [class.unassigned]="row.unassigned">
            <span class="avatar">{{ row.initials }}</span>
            <span class="name">{{ row.name }}</span>
            <span class="count">{{ row.countText }}</span>
          </div>
        } @empty {
          <p class="muted">No notes yet.</p>
        }
      </div>

      <span class="label">Review link</span>
      <div class="link-row">
        <input readonly [value]="reviewLink">
        <button mat-stroked-button (click)="copyLink()">
          <mat-icon>content_copy</mat-icon> Copy link
        </button>
      </div>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="close()">Close</button>
      <button mat-raised-button color="primary" (click)="openReview()">Open review view</button>
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    /* The scrollbar here was never a height problem. Material gives a dialog that has
       actions a padding of 20px 24px 0 — no bottom padding — and the last thing in this
       content is a button, whose .mat-mdc-button-touch-target is 48px tall and centred, so
       it hangs ~6px below a 36px button, overflows the content box and trips overflow:auto.
       The bottom padding absorbs it. Specificity: Material's rule is two classes, so this
       needs the class as well as the element to win.
       The height cap can then do what it was meant to — expand to 600px, then scroll —
       with the second term guarding a window too short for that (the space available is the
       window minus this dialog's own chrome, not a fraction of it). */
    mat-dialog-content.share-content {
      min-width: 480px;
      max-width: 560px;
      max-height: min(600px, calc(100vh - 190px));
      padding-bottom: 20px;
    }
    .intro { color: var(--text-secondary); font-size: 13px; margin: 0 0 10px 0; }
    .label { display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; }
    .rows { display: flex; flex-direction: column; gap: 5px; margin-bottom: 12px; }
    .row { display: flex; align-items: center; gap: 10px; padding: 7px 12px; border: 1px solid var(--border-default); border-radius: 6px; }
    .row.unassigned .name, .row.unassigned .count { color: var(--text-tertiary); }
    .avatar { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px;
      border-radius: 50%; background: var(--bg-secondary); font-size: 11px; font-weight: 600; flex-shrink: 0; }
    .name { flex: 1; font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .count { font-size: 12px; color: var(--text-secondary); }
    .muted { color: var(--text-tertiary); font-size: 13px; margin: 0; }
    .link-row { display: flex; gap: 8px; }
    .link-row input { flex: 1; min-width: 0; font: inherit; font-size: 13px; padding: 8px 10px;
      border: 1px solid var(--border-default); border-radius: 6px; background: var(--bg-secondary); color: var(--text-primary); }
    mat-dialog-actions { padding: 12px 24px; border-top: 1px solid var(--border-default); }
  `]
})
export class ShareReviewDialogComponent {
  rows: ReviewerRow[] = [];
  reviewLink: string;

  constructor(
    private dialogRef: MatDialogRef<ShareReviewDialogComponent>,
    private router: Router,
    private snackBar: MatSnackBar,
    @Inject(MAT_DIALOG_DATA) public data: ShareReviewDialogData
  ) {
    this.reviewLink = `${window.location.origin}/releases/${data.jobId}/review`;
    this.rows = this.buildRows(data.items || []);
  }

  private buildRows(items: ReleaseNoteItem[]): ReviewerRow[] {
    const byReviewer = new Map<string, { email: string; total: number; reviewed: number }>();
    let unassigned = 0;
    for (const item of items) {
      if (!item.reviewer_id) {
        unassigned++;
        continue;
      }
      const row = byReviewer.get(item.reviewer_id)
        || { email: item.reviewer_email || 'Someone', total: 0, reviewed: 0 };
      row.total++;
      if (item.reviewed) row.reviewed++;
      byReviewer.set(item.reviewer_id, row);
    }

    const rows: ReviewerRow[] = [...byReviewer.values()].map(row => ({
      initials: this.initialsOf(row.email),
      name: row.email,
      countText: `${row.reviewed} of ${row.total} reviewed`,
      unassigned: false
    }));
    if (unassigned) {
      rows.push({
        initials: '–',
        name: 'Unassigned',
        countText: `${unassigned} note${unassigned === 1 ? '' : 's'} — nobody is reading these`,
        unassigned: true
      });
    }
    return rows;
  }

  private initialsOf(email: string): string {
    const parts = email.split('@')[0].split(/[._-]+/).filter(Boolean);
    return ((parts[0]?.[0] || '?') + (parts[1]?.[0] || '')).toUpperCase();
  }

  copyLink(): void {
    // Not every browser/context grants clipboard access; say so rather than failing silently.
    navigator.clipboard?.writeText(this.reviewLink).then(
      () => this.snackBar.open('Review link copied', 'Close', { duration: 2000 }),
      () => this.snackBar.open('Could not copy — select the link and copy it', 'Close', { duration: 4000 })
    );
  }

  openReview(): void {
    this.dialogRef.close();
    this.router.navigate(['/releases', this.data.jobId, 'review']);
  }

  close(): void {
    this.dialogRef.close();
  }
}
