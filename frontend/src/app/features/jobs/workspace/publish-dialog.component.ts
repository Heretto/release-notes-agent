import { Component, Inject, ChangeDetectionStrategy, inject } from '@angular/core';
import { MatDialog, MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { openHerettoFolderBrowser } from '@heretto/hop-ui';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { HopHerettoService } from '@heretto/hop-ui';
import { JobsService, PublishResponse, PublishResult, ReleaseNoteTopic } from '../../../core/services/jobs.service';

export interface PublishDialogData {
  jobId: string;
  topics: ReleaseNoteTopic[];
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
/** One topic, and what it will be called in Heretto. */
interface PublishFile {
  topicId: string;
  title: string;
  filename: string;
}

@Component({
  selector: 'app-publish-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule,
    MatFormFieldModule, MatInputModule],
  template: `
    <h2 mat-dialog-title>{{ results ? heading : 'Publish to Heretto' }}</h2>

    <mat-dialog-content>
      @if (!results) {
        <p class="intro">
          Create or update {{ files.length }} topic{{ files.length === 1 ? '' : 's' }} with the
          current release notes.
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

        <span class="label files-label">
          File name{{ files.length === 1 ? '' : 's' }}
          @if (checkingFolder) { <span class="muted"> · checking the folder…</span> }
        </span>
        @for (file of files; track file.topicId) {
          <div class="file">
            <mat-form-field appearance="outline" subscriptSizing="dynamic" class="file-field">
              <mat-label>{{ file.title }}</mat-label>
              <input matInput class="mono" [value]="file.filename" [disabled]="publishing"
                     (input)="rename(file, $any($event.target).value)">
            </mat-form-field>
            @if (collision(file)) {
              <p class="overwrite">
                <mat-icon>warning</mat-icon>
                A file called <code>{{ file.filename }}</code> is already in this folder. Publishing
                will overwrite it.
              </p>
            }
          </div>
        }

        @if (publishing) {
          <div class="working">
            <mat-spinner diameter="20"></mat-spinner>
            <span>Publishing {{ files.length }} topic{{ files.length === 1 ? '' : 's' }}…</span>
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
    .files-label { margin-top: 18px; }
    .file { margin-bottom: 10px; }
    .file-field { width: 100%; }
    .mono { font-family: var(--font-mono); font-size: 13px; }
    .overwrite { display: flex; align-items: flex-start; gap: 6px; margin: 6px 0 0;
      font-size: 12px; line-height: 1.5; color: var(--color-warning-text); }
    .overwrite mat-icon { font-size: 16px; width: 16px; height: 16px; flex-shrink: 0; }
    .overwrite code { font-family: var(--font-mono); }
    mat-dialog-actions { padding: 14px 24px; border-top: 1px solid var(--border-default); }
  `]
})
export class PublishDialogComponent {
  private dialog = inject(MatDialog);
  private jobsService = inject(JobsService);
  private heretto = inject(HopHerettoService);

  /** Set when a different folder was picked for this publish. */
  chosenId: string | null = null;
  chosenCredentialId: string | null = null;
  chosenPath = '';

  publishing = false;
  error = '';

  /** The names to publish under; editable, and kept when the publish succeeds. */
  files: PublishFile[] = [];
  /** File names already in the destination folder, lower-cased. */
  private taken = new Set<string>();
  checkingFolder = false;
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
    this.files = data.topics.map(topic => ({
      topicId: topic.id, title: topic.title, filename: topic.filename,
    }));
    this.checkFolder();
  }

  /**
   * What is already in the destination folder, so a name that would overwrite can say so.
   *
   * Advisory only: the warning needs a connection id to browse with, which instruction
   * sets saved before that was recorded do not have. Publishing protects itself regardless
   * — it finds a file of the same name and updates it rather than creating a second one.
   */
  private checkFolder(): void {
    const credentialId = this.chosenCredentialId || this.data.credentialId;
    const folderId = this.folderId;
    this.taken = new Set();
    if (!credentialId || !folderId) return;

    this.checkingFolder = true;
    this.heretto.openFolder(credentialId, folderId).subscribe({
      next: listing => {
        this.checkingFolder = false;
        this.taken = new Set(
          listing.entries.filter(entry => entry.kind !== 'folder')
            .map(entry => entry.name.trim().toLowerCase()),
        );
      },
      error: () => this.checkingFolder = false,
    });
  }

  /** True when this name is already a file in the folder — publishing overwrites it. */
  collision(file: PublishFile): boolean {
    return this.taken.has(this.normalize(file.filename).toLowerCase());
  }

  rename(file: PublishFile, value: string): void {
    file.filename = value;
  }

  /** The same shape the server enforces, so the warning matches what will be written. */
  private normalize(name: string): string {
    const base = (name || '').trim().split(/[\\/]/).pop() || '';
    const stem = base.toLowerCase().endsWith('.dita') ? base.slice(0, -5) : base;
    const safe = stem.replace(/[^\w.\-]/g, '-').replace(/^[-.]+|[-.]+$/g, '');
    return `${safe || 'release-notes'}.dita`;
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
      this.checkFolder();   // a different folder has different names in it
    });
  }

  revert(): void {
    this.chosenId = null;
    this.chosenCredentialId = null;
    this.chosenPath = '';
    this.checkFolder();
  }

  publish(): void {
    if (this.publishing) return;
    this.publishing = true;
    this.error = '';
    this.jobsService.publish(this.data.jobId, {
      folderId: this.chosenId || undefined,
      credentialId: this.chosenCredentialId || undefined,
      filenames: this.files.map(file => ({ topic_id: file.topicId, filename: file.filename })),
    }).subscribe({
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
