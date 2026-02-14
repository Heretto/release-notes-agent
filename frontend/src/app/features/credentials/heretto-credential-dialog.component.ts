import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { HerettoCredential } from '../../core/services/credentials.service';

@Component({
  selector: 'app-heretto-credential-dialog',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <h2 mat-dialog-title>{{ data ? 'Edit' : 'Add' }} Heretto Credential</h2>
    <mat-dialog-content>
      <div *ngIf="data" class="current-values">
        <div class="info-box">
          <mat-icon>info</mat-icon>
          <span>Current credential details:</span>
        </div>
        <div class="credential-display">
          <div class="field-display">
            <strong>Server URL:</strong> {{ data.server_url }}
          </div>
          <div class="field-display">
            <strong>Username:</strong> {{ data.username }}
          </div>
          <div class="field-display">
            <strong>Token:</strong> {{ maskToken(data.token) }}
          </div>
        </div>
      </div>

      <form [formGroup]="form">
        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Name</mat-label>
          <input matInput formControlName="name" required>
          <mat-error *ngIf="form.get('name')?.hasError('required')">
            Name is required
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Server URL</mat-label>
          <input matInput formControlName="server_url"
                 placeholder="https://your-heretto-instance.com" required>
          <mat-hint *ngIf="data">Leave unchanged or enter new URL</mat-hint>
          <mat-error *ngIf="form.get('server_url')?.hasError('required')">
            Server URL is required
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Username</mat-label>
          <input matInput formControlName="username" required>
          <mat-hint *ngIf="data">Leave unchanged or enter new username</mat-hint>
          <mat-error *ngIf="form.get('username')?.hasError('required')">
            Username is required
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Token</mat-label>
          <input matInput type="password" formControlName="token"
                 [placeholder]="data ? 'Enter new token (leave empty to keep current)' : 'Enter token'"
                 [required]="!data">
          <mat-hint *ngIf="data">Leave empty to keep current token</mat-hint>
          <mat-error *ngIf="form.get('token')?.hasError('required')">
            Token is required
          </mat-error>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
      <button mat-raised-button color="primary"
              [disabled]="!form.valid"
              (click)="onSave()">Save</button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content {
      padding-top: 20px;
      min-width: 400px;
    }
    .full-width {
      width: 100%;
      margin-bottom: 15px;
    }
    .current-values {
      background: #f5f5f5;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;
      border: 1px solid #e0e0e0;
    }
    .info-box {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
      color: #1976d2;
      font-weight: 500;
    }
    .credential-display {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .field-display {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 0;
      word-break: break-all;
    }
    .field-display strong {
      min-width: 100px;
      color: #666;
    }
  `]
})
export class HerettoCredentialDialogComponent {
  form: FormGroup;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<HerettoCredentialDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: HerettoCredential | null
  ) {
    this.form = this.fb.group({
      name: [data?.name || '', Validators.required],
      server_url: [data?.server_url || '', Validators.required],
      username: [data?.username || '', Validators.required],
      token: ['', data ? [] : Validators.required]
    });
  }

  maskToken(token: string): string {
    if (!token) return '';
    if (token.length <= 8) return '****';
    return token.substring(0, 4) + '*'.repeat(token.length - 8) + token.substring(token.length - 4);
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    if (this.form.valid) {
      const formValue = this.form.value;
      if (this.data && !formValue.token) {
        delete formValue.token;
      }
      this.dialogRef.close(formValue);
    }
  }
}
