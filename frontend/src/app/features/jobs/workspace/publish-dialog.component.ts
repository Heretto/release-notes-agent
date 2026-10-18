import { Component, Inject, ChangeDetectionStrategy, inject } from '@angular/core';
import { MatDialog, MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { openHerettoFolderBrowser } from '@heretto/hop-ui';
import { JobsService, PublishResponse, PublishResult } from '../../../core/services/jobs.service';

export interface PublishDialogData {
  jobId: string;
  topicCount: number;
  /** Where this release publishes today — its own folder, or its instruction set's. */
  folderId: string | null;
  /** The Heretto that folder is in, when the instruction set recorded one. */
  credentialId: string | null;
  /** True when that folder comes from the instruction set rather than the release. */
  usual: boolean;
}

export interface PublishDialogResult {
  /** True when anything was published, so the workspace knows to reload. */
  published: boolean;
}

/**
 * Publish to Heretto: choose where, watch it happen, and open what came out.
 *
 * The dialog does the publishing rather than handing the job back to the workspace,
 * because the result is the part worth seeing — what landed, and a way into the folder it
 * landed in. Reported through a toast that replaces itself, that was gone before anyone
 * could use it.
 *
 * The folder can be changed for this publish only. A one-off destination that quietly
 * became the release's default is how notes end up somewhere nobody expects on the next
 * run, so nothing here is saved.
 */
@Component({
  selector: 'app-publish-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  template: `
    <h2 mat-dialog-title>{{ results ? heading : 'Publish to Heretto' }}</h2>

    <mat-dialog-content>
      @if (!results) {
        <p class="intro">
          Create or update {{ data.topicCount }} topic{{ data.topicCount === 1 ? '' : 's' }} with
          the current release notes.
        </p>

        <span class="label">Destination</span>
        <div class="folder">
          <mat-icon>folder</mat-icon>
          <div class="folder-text">
            @if (chosenPath) {
              <span class="path" [title]="chosenPath">{{ chosenPath }}</span>
              <span class="muted">Just for this publish — the release keeps its own folder.</span>
            } @else if (folderId) {
              <span class="path" [title]="folderId">{{ folderId }}</span>
              <span class="muted">
                {{ data.usual ? "The instruction set's folder" : "This release's folder" }}
              </span>
            } @else {
              <span class="path none">No folder set</span>
              <span class="muted">Choose one, or set it on the instruction set.</span>
            }
          </div>
          <button mat-stroked-button [disabled]="publishing" (click)="chooseFolder()">
            {{ folderId ? 'Change' : 'Choose…' }}
          </button>
        </div>
        @if (chosenPath) {
          <button mat-button class="revert" [disabled]="publishing" (click)="revert()">
            Use the usual folder
          </button>
        }

        @if (publishing) {
          <div class="working">
            <mat-spinner diameter="20"></mat-spinner>
            <span>Publishing {{ data.topicCount }} topic{{ data.topicCount === 1 ? '' : 's' }}…</span>
          </div>
        }
        @if (error) {
          <p class="failure">{{ error }}</p>
        }
      } @else {
        <ul class="results">
          @for (result of results; track $index) {
            <li [class.failed]="!result.success">
              <mat-icon class="mark">{{ result.success ? 'check_circle' : 'error' }}</mat-icon>
              <div class="result-text">
                <span class="result-title">{{ result.title || 'Topic' }}</span>
                @if (!result.success) { <span class="muted">{{ result.message }}</span> }
              </div>
            </li>
          }
        </ul>

        @if (outcome?.folder_url) {
          <a mat-flat-button color="primary" class="open-folder"
             [href]="outcome!.folder_url!" target="_blank" rel="noopener">
            <mat-icon>folder_open</mat-icon> Open the folder in Heretto
          </a>
        }
      }
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      @if (!results) {
        <button mat-button [disabled]="publishing" (click)="cancel()">Cancel</button>
        <button mat-raised-button color="primary" [disabled]="!folderId || publishing" (click)="publish()">
          Publish
        </button>
      } @else {
        <button mat-raised-button color="primary" (click)="done()">Done</button>
      }
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    mat-dialog-content { min-width: 460px; max-width: 540px; padding-bottom: 20px; }
    .intro { margin: 0 0 16px; font-size: 14px; color: var(--text-secondary); }
    .label { display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; }
    .folder { display: flex; align-items: center; gap: 10px; border: 1px solid var(--border-default);
      border-radius: 6px; padding: 10px 12px; }
    .folder-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
    .path { font-family: var(--font-mono); font-size: 13px; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap; }
    .path.none { font-family: inherit; color: var(--text-tertiary); }
    .muted { font-size: 12px; color: var(--text-tertiary); }
    .revert { margin-top: 6px; }
    .working { display: flex; align-items: center; gap: 10px; margin-top: 16px; font-size: 13px;
      color: var(--text-secondary); }
    .failure { margin: 16px 0 0; font-size: 13px; color: var(--color-error-text); }

    .results { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
    .results li { display: flex; align-items: center; gap: 10px; padding: 10px 0; }
    .results li + li { border-top: 1px solid var(--border-light); }
    .mark { color: var(--color-success-text); flex-shrink: 0; }
    .failed .mark { color: var(--color-error-text); }
    .result-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
    .result-title { font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .open-folder { margin-top: 16px; width: 100%; }
    mat-dialog-actions { padding: 14px 24px; border-top: 1px solid var(--border-default); }
  `]
})
export class PublishDialogComponent {
  private dialog = inject(MatDialog);
  private jobsService = inject(JobsService);

  /** Set when a different folder was picked for this publish. */
  chosenId: string | null = null;
  chosenCredentialId: string | null = null;
  chosenPath = '';

  publishing = false;
  error = '';
  /** Null until a publish has finished; then what came back. */
  outcome: PublishResponse | null = null;

  get results(): PublishResult[] | null {
    return this.outcome?.results ?? null;
  }

  constructor(
    private dialogRef: MatDialogRef<PublishDialogComponent, PublishDialogResult | undefined>,
    @Inject(MAT_DIALOG_DATA) public data: PublishDialogData
  ) {
    // Closing mid-publish would lose the links, which are the point of staying.
    dialogRef.disableClose = true;
  }

  get folderId(): string | null {
    return this.chosenId || this.data.folderId;
  }

  get heading(): string {
    const failed = (this.results || []).filter(result => !result.success).length;
    if (!failed) return 'Published to Heretto';
    return failed === this.results!.length ? 'Publishing failed' : 'Published with problems';
  }

  chooseFolder(): void {
    openHerettoFolderBrowser(this.dialog, {
      title: 'Publish these topics where?',
      purpose: 'Used for this publish only.',
      folderId: this.folderId,
      credentialId: this.chosenCredentialId || this.data.credentialId,
    }).subscribe(folder => {
      if (!folder) return;
      this.chosenId = folder.id;
      // A folder id is only meaningful in the Heretto it was chosen from.
      this.chosenCredentialId = folder.credential_id;
      this.chosenPath = folder.path || folder.name;
    });
  }

  revert(): void {
    this.chosenId = null;
    this.chosenCredentialId = null;
    this.chosenPath = '';
  }

  publish(): void {
    if (this.publishing) return;
    this.publishing = true;
    this.error = '';
    this.jobsService.publish(
      this.data.jobId, this.chosenId || undefined, this.chosenCredentialId || undefined,
    ).subscribe({
      next: outcome => {
        this.publishing = false;
        this.dialogRef.disableClose = false;
        this.outcome = outcome;
      },
      error: error => {
        this.publishing = false;
        this.dialogRef.disableClose = false;
        // Nothing was published, so the dialog stays on the form to be retried.
        this.error = error.error?.detail || 'Publishing failed.';
      }
    });
  }

  done(): void {
    this.dialogRef.close({ published: (this.results || []).some(result => result.success) });
  }

  cancel(): void {
    this.dialogRef.close();
  }
}
