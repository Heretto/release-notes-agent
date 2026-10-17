import { Component, Inject, ChangeDetectionStrategy, inject } from '@angular/core';
import { MatDialog, MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { openHerettoFolderBrowser } from '@heretto/hop-ui';

export interface PublishDialogData {
  topicCount: number;
  /** Where this release publishes today — its own folder, or its instruction set's. */
  folderId: string | null;
  /** True when that folder comes from the instruction set rather than the release. */
  usual: boolean;
}

export interface PublishDialogResult {
  /** Set only when the person chose somewhere other than the usual folder. */
  folderId: string | null;
}

/**
 * Confirm a publish, and say where it is going.
 *
 * The folder can be changed for this publish only. A one-off destination that quietly
 * became the release's default is how notes end up somewhere nobody expects on the next
 * run, so nothing here is saved.
 */
@Component({
  selector: 'app-publish-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule],
  template: `
    <h2 mat-dialog-title>Publish to Heretto</h2>

    <mat-dialog-content>
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
        <button mat-stroked-button (click)="chooseFolder()">
          {{ folderId ? 'Change' : 'Choose…' }}
        </button>
      </div>
      @if (chosenPath) {
        <button mat-button class="revert" (click)="revert()">Use the usual folder</button>
      }
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="cancel()">Cancel</button>
      <button mat-raised-button color="primary" [disabled]="!folderId" (click)="publish()">
        Publish
      </button>
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    mat-dialog-content { min-width: 460px; max-width: 520px; padding-bottom: 20px; }
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
    mat-dialog-actions { padding: 14px 24px; border-top: 1px solid var(--border-default); }
  `]
})
export class PublishDialogComponent {
  private dialog = inject(MatDialog);

  /** Set when a different folder was picked for this publish. */
  chosenId: string | null = null;
  chosenPath = '';

  constructor(
    private dialogRef: MatDialogRef<PublishDialogComponent, PublishDialogResult | undefined>,
    @Inject(MAT_DIALOG_DATA) public data: PublishDialogData
  ) {}

  get folderId(): string | null {
    return this.chosenId || this.data.folderId;
  }

  chooseFolder(): void {
    openHerettoFolderBrowser(this.dialog, {
      title: 'Publish these topics where?',
      purpose: 'Used for this publish only.',
      folderId: this.folderId,
    }).subscribe(folder => {
      if (!folder) return;
      this.chosenId = folder.id;
      this.chosenPath = folder.path || folder.name;
    });
  }

  revert(): void {
    this.chosenId = null;
    this.chosenPath = '';
  }

  publish(): void {
    this.dialogRef.close({ folderId: this.chosenId });
  }

  cancel(): void {
    this.dialogRef.close();
  }
}
