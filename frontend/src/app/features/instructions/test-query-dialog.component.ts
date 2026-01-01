import { Component, Inject, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatSelectModule } from '@angular/material/select';
import { MatDividerModule } from '@angular/material/divider';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { FormsModule } from '@angular/forms';
import { InstructionSet, InstructionsService } from '../../core/services/instructions.service';
import { CredentialsService, JiraCredential } from '../../core/services/credentials.service';

interface TestResult {
  success: boolean;
  instruction_set: {
    name: string;
    jql_query: string;
  };
  jira_credential?: {
    name: string;
    server: string;
  };
  results?: {
    total_found: number;
    limited_to: number;
    issues: Array<{
      key: string;
      summary: string;
      type: string;
      status: string;
      priority: string;
      created: string;
      labels: string[];
      components: string[];
    }>;
  };
  error?: string;
  message: string;
}

@Component({
  selector: 'app-test-query-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTableModule,
    MatChipsModule,
    MatExpansionModule,
    MatSelectModule,
    MatDividerModule,
    MatSnackBarModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon>bug_report</mat-icon>
      Test JQL Query
    </h2>

    <mat-dialog-content>
      <!-- Credential Selection -->
      <div class="credential-section" *ngIf="!testing && !testResult">
        <h3>Select Jira Credentials</h3>
        
        <div *ngIf="loadingCredentials" class="loading">
          <mat-spinner diameter="30"></mat-spinner>
          <p>Loading credentials...</p>
        </div>

        <div *ngIf="!loadingCredentials && jiraCredentials.length === 0" class="no-credentials">
          <mat-icon>warning</mat-icon>
          <p>No Jira credentials configured</p>
          <p class="hint">Please add Jira credentials in the Credentials section first.</p>
        </div>

        <mat-form-field *ngIf="!loadingCredentials && jiraCredentials.length > 0" class="full-width">
          <mat-label>Jira Credential</mat-label>
          <mat-select [(ngModel)]="selectedCredentialId">
            <mat-option *ngFor="let cred of jiraCredentials" [value]="cred.id">
              {{ cred.name }} ({{ cred.server_url }})
            </mat-option>
          </mat-select>
        </mat-form-field>

        <div class="query-info">
          <h4>Query to Test:</h4>
          <pre class="jql-query">{{ data.jql_query }}</pre>
        </div>
      </div>

      <!-- Testing State -->
      <div *ngIf="testing" class="testing-state">
        <mat-spinner></mat-spinner>
        <h3>Testing Query...</h3>
        <p>Executing: {{ data.jql_query }}</p>
        <p class="hint">This may take a few seconds depending on your Jira instance.</p>
      </div>

      <!-- Test Results -->
      <div *ngIf="testResult" class="results-section">
        <!-- Success Header -->
        <div class="result-header" [class.success]="testResult.success" [class.error]="!testResult.success">
          <mat-icon>{{ testResult.success ? 'check_circle' : 'error' }}</mat-icon>
          <div>
            <h3>{{ testResult.success ? 'Query Successful' : 'Query Failed' }}</h3>
            <p>{{ testResult.message }}</p>
          </div>
        </div>

        <!-- Connection Info -->
        <div *ngIf="testResult.jira_credential" class="connection-info">
          <p><strong>Server:</strong> {{ testResult.jira_credential.server }}</p>
          <p><strong>Credential:</strong> {{ testResult.jira_credential.name }}</p>
        </div>

        <mat-divider></mat-divider>

        <!-- Error Details -->
        <div *ngIf="!testResult.success && testResult.error" class="error-details">
          <h4>Error Details:</h4>
          <pre class="error-message">{{ testResult.error }}</pre>
        </div>

        <!-- Issues Table -->
        <div *ngIf="testResult.success && testResult.results" class="issues-section">
          <h4>
            Found {{ testResult.results.total_found }} issue(s)
            <span *ngIf="testResult.results.total_found > testResult.results.limited_to">
              (showing first {{ testResult.results.limited_to }})
            </span>
          </h4>

          <div *ngIf="testResult.results.issues.length === 0" class="no-issues">
            <mat-icon>inbox</mat-icon>
            <p>No issues match this query</p>
          </div>

          <table mat-table [dataSource]="testResult.results.issues" class="issues-table" 
                 *ngIf="testResult.results.issues.length > 0">
            
            <!-- Key Column -->
            <ng-container matColumnDef="key">
              <th mat-header-cell *matHeaderCellDef>Key</th>
              <td mat-cell *matCellDef="let issue">
                <strong>{{ issue.key }}</strong>
              </td>
            </ng-container>

            <!-- Summary Column -->
            <ng-container matColumnDef="summary">
              <th mat-header-cell *matHeaderCellDef>Summary</th>
              <td mat-cell *matCellDef="let issue" class="summary-cell">
                {{ issue.summary }}
              </td>
            </ng-container>

            <!-- Type Column -->
            <ng-container matColumnDef="type">
              <th mat-header-cell *matHeaderCellDef>Type</th>
              <td mat-cell *matCellDef="let issue">
                <mat-chip size="small">{{ issue.type }}</mat-chip>
              </td>
            </ng-container>

            <!-- Status Column -->
            <ng-container matColumnDef="status">
              <th mat-header-cell *matHeaderCellDef>Status</th>
              <td mat-cell *matCellDef="let issue">
                <mat-chip size="small" [class]="getStatusClass(issue.status)">
                  {{ issue.status }}
                </mat-chip>
              </td>
            </ng-container>

            <!-- Priority Column -->
            <ng-container matColumnDef="priority">
              <th mat-header-cell *matHeaderCellDef>Priority</th>
              <td mat-cell *matCellDef="let issue">
                <mat-chip size="small" *ngIf="issue.priority" 
                          [class]="getPriorityClass(issue.priority)">
                  {{ issue.priority }}
                </mat-chip>
                <span *ngIf="!issue.priority">-</span>
              </td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
          </table>

          <!-- Expanded Details -->
          <mat-expansion-panel *ngIf="testResult.results.issues.length > 0" class="details-panel">
            <mat-expansion-panel-header>
              <mat-panel-title>
                <mat-icon>info</mat-icon>
                Additional Details
              </mat-panel-title>
            </mat-expansion-panel-header>
            
            <div class="issue-details" *ngFor="let issue of testResult.results.issues">
              <h5>{{ issue.key }}: {{ issue.summary }}</h5>
              
              <div class="detail-row" *ngIf="issue.labels && issue.labels.length > 0">
                <strong>Labels:</strong>
                <div class="chip-list">
                  <mat-chip *ngFor="let label of issue.labels" size="small">{{ label }}</mat-chip>
                </div>
              </div>
              
              <div class="detail-row" *ngIf="issue.components && issue.components.length > 0">
                <strong>Components:</strong>
                <div class="chip-list">
                  <mat-chip *ngFor="let component of issue.components" size="small">{{ component }}</mat-chip>
                </div>
              </div>
              
              <div class="detail-row" *ngIf="issue.created">
                <strong>Created:</strong>
                <span>{{ formatDate(issue.created) }}</span>
              </div>
              
              <mat-divider></mat-divider>
            </div>
          </mat-expansion-panel>
        </div>
      </div>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="close()" *ngIf="!testing">Close</button>
      <button mat-button (click)="reset()" *ngIf="testResult && !testing">
        <mat-icon>refresh</mat-icon>
        Test Again
      </button>
      <button mat-raised-button color="primary" 
              (click)="runTest()"
              [disabled]="!selectedCredentialId || testing"
              *ngIf="!testResult && jiraCredentials.length > 0">
        <mat-icon>play_arrow</mat-icon>
        Run Test
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content {
      min-width: 700px;
      max-width: 900px;
      max-height: 70vh;
      overflow-y: auto;
    }

    h2 {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .credential-section {
      padding: 20px 0;
    }

    .credential-section h3 {
      margin-bottom: 15px;
      color: #333;
    }

    .full-width {
      width: 100%;
    }

    .loading, .testing-state {
      text-align: center;
      padding: 40px;
    }

    .loading mat-spinner, .testing-state mat-spinner {
      margin: 0 auto 20px;
    }

    .no-credentials {
      text-align: center;
      padding: 30px;
      background: #f5f5f5;
      border-radius: 8px;
    }

    .no-credentials mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #ff9800;
      margin: 0 auto 10px;
    }

    .hint {
      color: #666;
      font-size: 14px;
      margin-top: 5px;
    }

    .query-info {
      margin-top: 20px;
      padding: 15px;
      background: #f9f9f9;
      border-radius: 8px;
    }

    .query-info h4 {
      margin: 0 0 10px 0;
      color: #666;
      font-size: 14px;
    }

    .jql-query {
      background: white;
      padding: 12px;
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      font-family: monospace;
      font-size: 13px;
      margin: 0;
      white-space: pre-wrap;
    }

    .result-header {
      display: flex;
      align-items: center;
      gap: 15px;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 20px;
    }

    .result-header.success {
      background: #e8f5e9;
      color: #2e7d32;
    }

    .result-header.error {
      background: #ffebee;
      color: #c62828;
    }

    .result-header mat-icon {
      font-size: 36px;
      width: 36px;
      height: 36px;
    }

    .result-header h3 {
      margin: 0;
      font-size: 18px;
    }

    .result-header p {
      margin: 5px 0 0 0;
      font-size: 14px;
    }

    .connection-info {
      padding: 10px 20px;
      background: #f5f5f5;
      border-radius: 4px;
      margin-bottom: 20px;
    }

    .connection-info p {
      margin: 5px 0;
      font-size: 14px;
    }

    .error-details {
      padding: 20px;
      background: #fff3e0;
      border-radius: 8px;
      margin: 20px 0;
    }

    .error-details h4 {
      margin: 0 0 10px 0;
      color: #e65100;
    }

    .error-message {
      background: white;
      padding: 15px;
      border: 1px solid #ffcc80;
      border-radius: 4px;
      font-size: 13px;
      color: #d84315;
      white-space: pre-wrap;
      margin: 0;
    }

    .issues-section {
      padding: 20px 0;
    }

    .issues-section h4 {
      margin-bottom: 20px;
      color: #333;
    }

    .no-issues {
      text-align: center;
      padding: 40px;
      background: #f5f5f5;
      border-radius: 8px;
    }

    .no-issues mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #999;
      margin: 0 auto 10px;
    }

    .issues-table {
      width: 100%;
      margin-bottom: 20px;
    }

    .summary-cell {
      max-width: 300px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    mat-chip {
      font-size: 12px;
      min-height: 24px;
      padding: 4px 8px;
    }

    mat-chip.done {
      background-color: #4caf50 !important;
      color: white !important;
    }

    mat-chip.in-progress {
      background-color: #2196f3 !important;
      color: white !important;
    }

    mat-chip.todo {
      background-color: #9e9e9e !important;
      color: white !important;
    }

    mat-chip.critical, mat-chip.highest {
      background-color: #f44336 !important;
      color: white !important;
    }

    mat-chip.high {
      background-color: #ff9800 !important;
      color: white !important;
    }

    mat-chip.medium {
      background-color: #ffc107 !important;
      color: black !important;
    }

    mat-chip.low, mat-chip.lowest {
      background-color: #4caf50 !important;
      color: white !important;
    }

    .details-panel {
      margin-top: 20px;
    }

    .issue-details {
      padding: 15px 0;
    }

    .issue-details h5 {
      margin: 0 0 15px 0;
      color: #333;
    }

    .detail-row {
      margin: 10px 0;
      display: flex;
      align-items: flex-start;
      gap: 10px;
    }

    .detail-row strong {
      min-width: 100px;
      color: #666;
    }

    .chip-list {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }

    mat-divider {
      margin: 15px 0;
    }
  `]
})
export class TestQueryDialogComponent implements OnInit {
  private instructionsService = inject(InstructionsService);
  private credentialsService = inject(CredentialsService);
  private snackBar = inject(MatSnackBar);

  jiraCredentials: JiraCredential[] = [];
  selectedCredentialId: string | null = null;
  loadingCredentials = false;
  testing = false;
  testResult: TestResult | null = null;

  displayedColumns: string[] = ['key', 'summary', 'type', 'status', 'priority'];

  constructor(
    private dialogRef: MatDialogRef<TestQueryDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: InstructionSet
  ) {}

  ngOnInit() {
    this.loadJiraCredentials();
  }

  loadJiraCredentials() {
    this.loadingCredentials = true;
    this.credentialsService.getJiraCredentials().subscribe({
      next: (credentials) => {
        this.jiraCredentials = credentials;
        // Auto-select if only one credential
        if (credentials.length === 1) {
          this.selectedCredentialId = credentials[0].id!;
        }
        this.loadingCredentials = false;
      },
      error: (error) => {
        console.error('Failed to load Jira credentials:', error);
        this.loadingCredentials = false;
        this.snackBar.open('Failed to load Jira credentials', 'Close', {
          duration: 3000
        });
      }
    });
  }

  runTest() {
    if (!this.data.id || !this.selectedCredentialId) return;

    this.testing = true;
    
    // Call the test endpoint
    this.instructionsService.testQuery(this.data.id, this.selectedCredentialId).subscribe({
      next: (result) => {
        this.testResult = result;
        this.testing = false;
        
        if (result.success) {
          this.snackBar.open(
            `Query successful! Found ${result.results?.total_found || 0} issues`,
            'Close',
            { duration: 3000 }
          );
        }
      },
      error: (error) => {
        this.testing = false;
        this.testResult = {
          success: false,
          instruction_set: {
            name: this.data.name,
            jql_query: this.data.jql_query
          },
          error: error.error?.detail || error.message || 'Unknown error occurred',
          message: 'Failed to execute query'
        };
        
        this.snackBar.open('Query test failed', 'Close', {
          duration: 3000
        });
      }
    });
  }

  reset() {
    this.testResult = null;
    this.testing = false;
  }

  close() {
    this.dialogRef.close();
  }

  getStatusClass(status: string): string {
    const lower = status.toLowerCase();
    if (lower.includes('done') || lower.includes('closed')) return 'done';
    if (lower.includes('progress')) return 'in-progress';
    return 'todo';
  }

  getPriorityClass(priority: string): string {
    const lower = priority.toLowerCase();
    if (lower.includes('critical') || lower.includes('highest')) return 'critical';
    if (lower.includes('high')) return 'high';
    if (lower.includes('medium')) return 'medium';
    if (lower.includes('low')) return 'low';
    return '';
  }

  formatDate(dateStr: string): string {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  }
}