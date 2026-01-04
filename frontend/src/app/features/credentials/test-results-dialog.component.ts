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
        <div class="detail-row" *ngIf="data.timestamp">
          <strong>Timestamp:</strong>
          <span>{{ formatDate(data.timestamp) }}</span>
        </div>
      </div>

      <!-- Request Section for AI Providers -->
      <div class="result-section" *ngIf="data.request">
        <mat-divider></mat-divider>
        <mat-expansion-panel [expanded]="true">
          <mat-expansion-panel-header>
            <mat-panel-title>
              <mat-icon>send</mat-icon>
              Request Details
            </mat-panel-title>
            <mat-panel-description>
              {{ data.request.method || 'POST' }} {{ data.request.url }}
            </mat-panel-description>
          </mat-expansion-panel-header>
          
          <div class="request-content">
            <div class="url-section">
              <strong>URL:</strong>
              <code class="url-code">{{ data.request.url }}</code>
            </div>
            
            <div class="method-section">
              <strong>Method:</strong>
              <span class="method-badge">{{ data.request.method || 'POST' }}</span>
            </div>
            
            <div class="headers-section" *ngIf="data.request.headers">
              <strong>Headers:</strong>
              <pre class="json-response">{{ formatJson(data.request.headers) }}</pre>
            </div>
            
            <div class="body-section" *ngIf="data.request.body">
              <strong>Request Body:</strong>
              <pre class="json-response">{{ formatJson(data.request.body) }}</pre>
            </div>

            <!-- Legacy format for non-AI providers -->
            <div *ngIf="data.request.prompt && !data.request.body" class="detail-row">
              <strong>Model:</strong> {{ data.request.model }}
            </div>
            <div *ngIf="data.request.prompt && !data.request.body" class="detail-row">
              <strong>Prompt:</strong> {{ data.request.prompt }}
            </div>
            <div *ngIf="data.request.temperature !== undefined && !data.request.body" class="detail-row">
              <strong>Temperature:</strong> {{ data.request.temperature }}
            </div>
            <div *ngIf="data.request.max_tokens && !data.request.body" class="detail-row">
              <strong>Max Tokens:</strong> {{ data.request.max_tokens }}
            </div>
          </div>
        </mat-expansion-panel>
      </div>

      <!-- Response Section for AI Providers -->
      <div class="result-section" *ngIf="data.response">
        <mat-divider></mat-divider>
        <mat-expansion-panel [expanded]="data.success">
          <mat-expansion-panel-header>
            <mat-panel-title>
              <mat-icon>reply</mat-icon>
              Response Details
            </mat-panel-title>
            <mat-panel-description>
              {{ data.response.status_code || data.status_code }} {{ data.success ? 'OK' : 'Error' }}
            </mat-panel-description>
          </mat-expansion-panel-header>
          
          <div class="response-content">
            <div class="headers-section" *ngIf="data.response.headers">
              <strong>Response Headers:</strong>
              <pre class="json-response">{{ formatJson(data.response.headers) }}</pre>
            </div>
            
            <div class="available-models-section" *ngIf="data.response.available_models">
              <strong>Available Models:</strong>
              <div class="models-list">
                <mat-chip *ngFor="let model of data.response.available_models">
                  {{ model }}
                </mat-chip>
              </div>
            </div>
            
            <div class="body-section" *ngIf="data.response.body">
              <strong>Response Body:</strong>
              <pre class="json-response">{{ formatJson(data.response.body) }}</pre>
            </div>

            <!-- Legacy format -->
            <div *ngIf="data.response.model && !data.response.body" class="detail-row">
              <strong>Model Used:</strong> {{ data.response.model }}
            </div>
            <div *ngIf="data.response.content && !data.response.body" class="detail-row">
              <strong>Response:</strong> {{ data.response.content }}
            </div>
            <div *ngIf="data.response.finish_reason && !data.response.body" class="detail-row">
              <strong>Finish Reason:</strong> {{ data.response.finish_reason }}
            </div>
          </div>
        </mat-expansion-panel>
      </div>

      <!-- Jira specific response -->
      <div class="result-section" *ngIf="data.response_body && !data.response">
        <mat-divider></mat-divider>
        <h3>Response</h3>
        
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

      <!-- Response Headers for Jira -->
      <div class="result-section" *ngIf="data.response_headers && !data.response">
        <mat-divider></mat-divider>
        <mat-expansion-panel>
          <mat-expansion-panel-header>
            <mat-panel-title>
              Response Headers
            </mat-panel-title>
          </mat-expansion-panel-header>
          <pre class="json-response">{{ formatJson(data.response_headers) }}</pre>
        </mat-expansion-panel>
      </div>

      <!-- Error Details -->
      <div class="result-section error-section" *ngIf="data.error || data.error_details">
        <mat-divider></mat-divider>
        <h3>Error Details</h3>
        <pre class="error-text">{{ data.error || data.error_details }}</pre>
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
    
    .url-section, .method-section {
      margin-bottom: 10px;
    }
    
    .url-code {
      background: #f5f5f5;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
      display: inline-block;
      margin-left: 10px;
      word-break: break-all;
    }
    
    .method-badge {
      background: #2196f3;
      color: white;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 500;
      display: inline-block;
      margin-left: 10px;
    }
    
    .headers-section, .body-section {
      margin-top: 15px;
    }
    
    .headers-section strong, .body-section strong {
      display: block;
      margin-bottom: 8px;
      color: #666;
    }
    
    .request-content, .response-content {
      padding: 10px;
    }
    
    .available-models-section {
      margin: 15px 0;
    }
    
    .available-models-section strong {
      display: block;
      margin-bottom: 10px;
      color: #666;
    }
    
    .models-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      background: #f5f5f5;
      padding: 12px;
      border-radius: 4px;
    }
    
    .models-list mat-chip {
      background: #2196f3 !important;
      color: white !important;
      font-family: 'Courier New', monospace;
      font-size: 12px;
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