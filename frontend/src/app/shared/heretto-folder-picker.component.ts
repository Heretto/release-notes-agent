import { Component, Inject, OnInit, ChangeDetectionStrategy, inject } from '@angular/core';
import { MatDialog, MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Observable } from 'rxjs';
import {
  HerettoConnection, HerettoEntry, HerettoFolderListing, HerettoRepository, HopHerettoService,
} from '@heretto/hop-ui';

/** Where release notes get written: a folder, named so a person recognises it. */
export interface HerettoFolder {
  credential_id: string;
  folder_id: string;
  /** The repository path, for showing the choice back. Falls back to the folder name. */
  path: string;
}

export interface HerettoFolderPickerData {
  title?: string;
  purpose?: string;
  /** Open here, if the caller already has a folder. */
  folderId?: string | null;
  credentialId?: string | null;
}

/**
 * Choose a Heretto **folder**.
 *
 * hop-core ships a file browser (`openHerettoFileBrowser`), and it only ever returns a
 * file — there is no folder mode, and publishing needs a folder. This navigates with the
 * same service and types, so it follows hop-core's Heretto API rather than reimplementing
 * it, and returns the folder you are standing in.
 */
@Component({
  selector: 'app-heretto-folder-picker',
  standalone: true,
  imports: [
    MatDialogModule, MatButtonModule, MatIconModule, MatFormFieldModule, MatSelectModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.title || 'Choose a Heretto folder' }}</h2>

    <mat-dialog-content class="picker">
      @if (data.purpose) { <p class="purpose">{{ data.purpose }}</p> }

      @if (connections.length > 1) {
        <mat-form-field appearance="outline" subscriptSizing="dynamic" class="connection">
          <mat-label>Heretto connection</mat-label>
          <mat-select [value]="credentialId" (selectionChange)="useConnection($event.value)">
            @for (connection of connections; track connection.id) {
              <mat-option [value]="connection.id">{{ connection.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      }

      @if (repositories.length > 1 && !folder) {
        <mat-form-field appearance="outline" subscriptSizing="dynamic" class="connection">
          <mat-label>Repository</mat-label>
          <mat-select (selectionChange)="openRepository($event.value)">
            @for (repo of repositories; track repo.repository + repo.branch) {
              <mat-option [value]="repo">{{ repo.repository }} ({{ repo.branch }})</mat-option>
            }
          </mat-select>
        </mat-form-field>
      }

      @if (folder) {
        <div class="crumbs">
          <button mat-icon-button [disabled]="!folder.parent_id || loading"
                  (click)="open(folder.parent_id!)" matTooltip="Up one folder"
                  aria-label="Up one folder">
            <mat-icon>arrow_upward</mat-icon>
          </button>
          <span class="here" [title]="folder.path || folder.name">{{ folder.path || folder.name }}</span>
        </div>
      }

      <div class="listing">
        @if (loading) {
          <div class="centre"><mat-spinner diameter="28"></mat-spinner></div>
        } @else if (error) {
          <div class="centre error">
            <mat-icon>error</mat-icon>
            <span>{{ error }}</span>
          </div>
        } @else {
          @for (child of childFolders; track child.id) {
            <button type="button" class="row" (click)="open(child.id)">
              <mat-icon>folder</mat-icon>
              <span class="name">{{ child.name }}</span>
              <mat-icon class="chevron">chevron_right</mat-icon>
            </button>
          } @empty {
            <p class="centre muted">No folders in here. Select this one, or go up.</p>
          }
        }
      </div>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="close()">Cancel</button>
      <button mat-raised-button color="primary" [disabled]="!folder || loading" (click)="choose()">
        Select this folder
      </button>
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    mat-dialog-content.picker { width: 560px; max-width: 100%; padding-bottom: 20px; }
    .purpose { margin: 0 0 14px; font-size: 13px; color: var(--text-secondary); }
    .connection { width: 100%; margin-bottom: 12px; }
    .crumbs { display: flex; align-items: center; gap: 4px; margin-bottom: 8px; }
    .here { font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary);
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: rtl; text-align: left; }
    .listing { border: 1px solid var(--border-default); border-radius: 6px; min-height: 240px;
      max-height: 320px; overflow-y: auto; }
    .row { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left;
      padding: 9px 12px; border: none; background: none; font: inherit; color: inherit; cursor: pointer; }
    .row + .row { border-top: 1px solid var(--border-light); }
    .row:hover { background: var(--bg-secondary); }
    .row .name { flex: 1; font-size: 14px; }
    .row .chevron { color: var(--text-tertiary); }
    .centre { display: flex; align-items: center; justify-content: center; gap: 8px;
      padding: 40px 20px; text-align: center; font-size: 13px; }
    .centre.error { color: var(--color-error-text); }
    .muted { color: var(--text-tertiary); margin: 0; }
    mat-dialog-actions { padding: 14px 24px; border-top: 1px solid var(--border-default); }
  `]
})
export class HerettoFolderPickerComponent implements OnInit {
  private heretto = inject(HopHerettoService);

  connections: HerettoConnection[] = [];
  repositories: HerettoRepository[] = [];
  credentialId: string | null = null;
  folder: HerettoFolderListing | null = null;
  loading = false;
  error = '';

  constructor(
    private dialogRef: MatDialogRef<HerettoFolderPickerComponent, HerettoFolder | undefined>,
    @Inject(MAT_DIALOG_DATA) public data: HerettoFolderPickerData
  ) {}

  get childFolders(): HerettoEntry[] {
    return (this.folder?.entries || []).filter(entry => entry.kind === 'folder');
  }

  ngOnInit(): void {
    this.loading = true;
    this.heretto.connections().subscribe({
      next: connections => {
        this.connections = connections;
        const chosen = this.data.credentialId
          || (connections.length ? connections[0].id : null);
        if (chosen) this.useConnection(chosen);
        else this.fail('No Heretto connection is configured.');
      },
      error: () => this.fail('Could not load the Heretto connections.')
    });
  }

  useConnection(credentialId: string): void {
    this.credentialId = credentialId;
    this.folder = null;
    this.loading = true;
    this.error = '';

    // A folder we were given opens directly; otherwise start at the repository root.
    if (this.data.folderId) {
      this.run(this.heretto.openFolder(credentialId, this.data.folderId, true));
      return;
    }
    this.heretto.repositories(credentialId).subscribe({
      next: repositories => {
        this.repositories = repositories;
        if (repositories.length) this.openRepository(repositories[0]);
        else this.fail('That connection has no repositories.');
      },
      error: () => this.fail('Could not list the repositories.')
    });
  }

  openRepository(repo: HerettoRepository): void {
    if (!this.credentialId) return;
    this.loading = true;
    this.run(this.heretto.openRepository(this.credentialId, repo.branch, repo.repository));
  }

  open(folderId: string): void {
    if (!this.credentialId) return;
    this.loading = true;
    this.run(this.heretto.openFolder(this.credentialId, folderId, true));
  }

  private run(request: Observable<HerettoFolderListing>): void {
    this.error = '';
    request.subscribe({
      next: listing => {
        this.folder = listing;
        this.loading = false;
      },
      // The message is Heretto's problem to explain; say which step failed.
      error: () => this.fail('Could not open that folder.')
    });
  }

  private fail(message: string): void {
    this.loading = false;
    this.error = message;
  }

  choose(): void {
    if (!this.folder || !this.credentialId) return;
    this.dialogRef.close({
      credential_id: this.credentialId,
      folder_id: this.folder.id,
      path: this.folder.path || this.folder.name,
    });
  }

  close(): void {
    this.dialogRef.close();
  }
}

/** Open the folder picker; emits the chosen folder, or undefined if none was. */
export function openHerettoFolderPicker(
  dialog: MatDialog, data: HerettoFolderPickerData = {},
): Observable<HerettoFolder | undefined> {
  return dialog.open<HerettoFolderPickerComponent, HerettoFolderPickerData, HerettoFolder>(
    HerettoFolderPickerComponent, { data, width: '600px', maxWidth: 'calc(100vw - 32px)' },
  ).afterClosed();
}
