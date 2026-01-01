import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';

@Component({
  selector: 'app-test-results-dialog',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatExpansionModule,
    MatChipsModule,
    MatDividerModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon [class]="data.success ? 'success-icon' : 'error-icon'">
        {{ data.success ? 'check_circle' : 'error' }}
      </mat-icon>
      Test Connection Results
    </h2>
    
    <mat-dialog-content>
      <div class="result-section">
        <h3>Status</h3>
        <div class="status-row">
          <mat-chip [class]="getStatusClass()">
            HTTP {{ data.status_code }}
          </mat-chip>
          <span class="message">{{ data.message }}</span>
        </div>
      </div>

      <mat-divider></mat-divider>

      <div class="result-section" *ngIf="data.test_url">
        <h3>Test Details</h3>
        <div class="detail-row">
          <strong>Test URL:</strong>
          <code>{{ data.test_url }}</code>
        </div>
        <div class="detail-row">
          <strong>Timestamp:</strong>
          <span>{{ formatDate(data.timestamp) }}</span>
        </div>
      </div>

      <mat-divider *ngIf="data.response_body"></mat-divider>

      <div class="result-section" *ngIf="data.response_body">
        <h3>Response Body</h3>
        
        <div *ngIf="data.success && data.response_body.issues" class="issues-summary">
          <p><strong>Total Issues Found:</strong> {{ data.response_body.total }}</p>
          <p><strong>Recent Issues:</strong></p>
          
          <div class="issue-card" *ngFor="let issue of data.response_body.issues">
            <div class="issue-header">
              <strong>{{ issue.key }}</strong>
              <mat-chip size="small">{{ issue.status }}</mat-chip>
            </div>
            <div class="issue-summary">{{ issue.summary }}</div>
            <div class="issue-created">Created: {{ formatDate(issue.created) }}</div>
          </div>
        </div>

        <mat-expansion-panel *ngIf="!data.success || !data.response_body.issues">
          <mat-expansion-panel-header>
            <mat-panel-title>
              Raw Response
            </mat-panel-title>
          </mat-expansion-panel-header>
          <pre class="json-response">{{ formatJson(data.response_body) }}</pre>
        </mat-expansion-panel>
      </div>

      <mat-divider *ngIf="data.response_headers"></mat-divider>

      <div class="result-section" *ngIf="data.response_headers">
        <mat-expansion-panel>
          <mat-expansion-panel-header>
            <mat-panel-title>
              Response Headers
            </mat-panel-title>
          </mat-expansion-panel-header>
          <pre class="json-response">{{ formatJson(data.response_headers) }}</pre>
        </mat-expansion-panel>
      </div>

      <div class="result-section error-section" *ngIf="data.error_details">
        <h3>Error Details</h3>
        <pre class="error-text">{{ data.error_details }}</pre>
      </div>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-raised-button color="primary" (click)="close()">Close</button>
    </mat-dialog-actions>
  `,
  styles: [`
    :host {
      display: block;
      min-width: 600px;
      max-width: 800px;
    }

    mat-dialog-content {
      max-height: 600px;
      overflow-y: auto;
    }

    h2 {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .success-icon {
      color: #4caf50;
    }

    .error-icon {
      color: #f44336;
    }

    .result-section {
      margin: 20px 0;
    }

    .result-section h3 {
      margin-bottom: 10px;
      color: #666;
      font-size: 14px;
      font-weight: 500;
      text-transform: uppercase;
    }

    .status-row {
      display: flex;
      align-items: center;
      gap: 15px;
    }

    .message {
      flex: 1;
    }

    .detail-row {
      margin: 10px 0;
      display: flex;
      gap: 10px;
      align-items: baseline;
    }

    .detail-row strong {
      min-width: 100px;
    }

    .detail-row code {
      background: #f5f5f5;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
      word-break: break-all;
    }

    .issues-summary {
      background: #f9f9f9;
      padding: 15px;
      border-radius: 8px;
    }

    .issue-card {
      background: white;
      padding: 12px;
      margin: 10px 0;
      border-radius: 6px;
      border-left: 4px solid #2196f3;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    .issue-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .issue-summary {
      color: #333;
      margin-bottom: 8px;
    }

    .issue-created {
      font-size: 12px;
      color: #999;
    }

    .json-response {
      background: #1e1e1e;
      color: #d4d4d4;
      padding: 15px;
      border-radius: 4px;
      overflow-x: auto;
      font-size: 12px;
      line-height: 1.5;
      max-height: 300px;
    }

    .error-section {
      background: #ffebee;
      padding: 15px;
      border-radius: 8px;
    }

    .error-text {
      color: #c62828;
      font-size: 12px;
      white-space: pre-wrap;
    }

    mat-chip {
      font-size: 12px;
    }

    mat-chip.success {
      background-color: #4caf50 !important;
      color: white !important;
    }

    mat-chip.warning {
      background-color: #ff9800 !important;
      color: white !important;
    }

    mat-chip.error {
      background-color: #f44336 !important;
      color: white !important;
    }

    mat-expansion-panel {
      margin-top: 10px;
    }
  `]
})
export class TestResultsDialogComponent {
  constructor(
    private dialogRef: MatDialogRef<TestResultsDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: any
  ) {}

  close(): void {
    this.dialogRef.close();
  }

  getStatusClass(): string {
    if (this.data.status_code >= 200 && this.data.status_code < 300) {
      return 'success';
    } else if (this.data.status_code >= 400 && this.data.status_code < 500) {
      return 'warning';
    } else {
      return 'error';
    }
  }

  formatJson(obj: any): string {
    return JSON.stringify(obj, null, 2);
  }

  formatDate(dateStr: string): string {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  }
}