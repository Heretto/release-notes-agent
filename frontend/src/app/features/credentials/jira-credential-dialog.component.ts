import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { JiraCredential } from '../../core/services/credentials.service';

@Component({
  selector: 'app-jira-credential-dialog',
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
    <h2 mat-dialog-title>{{ data ? 'Edit' : 'Add' }} Jira Credential</h2>
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
            <strong>Email:</strong> {{ data.email }}
          </div>
          <div class="field-display">
            <strong>API Token:</strong> {{ maskApiToken(data.api_token) }}
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
                 placeholder="https://your-domain.atlassian.net" required>
          <mat-hint *ngIf="data">Leave unchanged or enter new URL</mat-hint>
          <mat-error *ngIf="form.get('server_url')?.hasError('required')">
            Server URL is required
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Email</mat-label>
          <input matInput type="email" formControlName="email" required>
          <mat-hint *ngIf="data">Leave unchanged or enter new email</mat-hint>
          <mat-error *ngIf="form.get('email')?.hasError('required')">
            Email is required
          </mat-error>
          <mat-error *ngIf="form.get('email')?.hasError('email')">
            Please enter a valid email
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>API Token</mat-label>
          <input matInput type="password" formControlName="api_token" 
                 [placeholder]="data ? 'Enter new token (leave empty to keep current)' : 'Enter API token'" 
                 [required]="!data">
          <mat-hint *ngIf="data">Leave empty to keep current token</mat-hint>
          <mat-error *ngIf="form.get('api_token')?.hasError('required')">
            API Token is required
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
export class JiraCredentialDialogComponent {
  form: FormGroup;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<JiraCredentialDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: JiraCredential | null
  ) {
    this.form = this.fb.group({
      name: [data?.name || '', Validators.required],
      server_url: [data?.server_url || '', Validators.required],
      email: [data?.email || '', [Validators.required, Validators.email]],
      api_token: ['', data ? [] : Validators.required] // Only required for new credentials
    });
  }

  maskApiToken(token: string): string {
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
      // If editing and api_token is empty, don't include it in the update
      if (this.data && !formValue.api_token) {
        delete formValue.api_token;
      }
      this.dialogRef.close(formValue);
    }
  }
}