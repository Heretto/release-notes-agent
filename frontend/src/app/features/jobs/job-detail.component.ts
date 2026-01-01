import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatDividerModule } from '@angular/material/divider';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { JobsService, Job } from '../../core/services/jobs.service';
import { CredentialsService, AICredential } from '../../core/services/credentials.service';
import { interval, Subscription } from 'rxjs';
import { switchMap, startWith } from 'rxjs/operators';

interface JobLog {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
  details?: any;
}

interface JobRequest {
  id: string;
  timestamp: string;
  type: 'jira_query' | 'ai_generation' | 'heretto_publish';
  request_data: any;
  response_data?: any;
  status: 'pending' | 'success' | 'failed';
  error_message?: string;
  duration_ms?: number;
}

interface JobArtifact {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

@Component({
  selector: 'app-job-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatProgressBarModule,
    MatExpansionModule,
    MatDividerModule,
    MatSnackBarModule,
    MatTooltipModule
  ],
  template: `
    <div class="job-detail-container">
      <div class="header">
        <button mat-icon-button (click)="navigateBack()" class="back-button">
          <mat-icon>arrow_back</mat-icon>
        </button>
        <div class="header-content">
          <h1>Job Details</h1>
          <p class="job-id" *ngIf="job">ID: {{ job.id }}</p>
        </div>
        <div class="header-actions" *ngIf="job">
          <button mat-raised-button color="primary" 
                  (click)="downloadArtifact()"
                  *ngIf="job.status === 'completed' && artifacts.length > 0">
            <mat-icon>download</mat-icon>
            Download Output
          </button>
          <button mat-raised-button color="accent" 
                  (click)="retryJob()"
                  *ngIf="job.status === 'failed'">
            <mat-icon>refresh</mat-icon>
            Retry Job
          </button>
          <button mat-raised-button color="warn" 
                  (click)="cancelJob()"
                  *ngIf="job.status === 'running' || job.status === 'pending'">
            <mat-icon>cancel</mat-icon>
            Cancel Job
          </button>
        </div>
      </div>

      <div *ngIf="loading" class="loading-container">
        <mat-spinner></mat-spinner>
        <p>Loading job details...</p>
      </div>

      <!-- Retry Progress Bar -->
      <div *ngIf="retryInProgress" class="retry-progress-container">
        <mat-card class="retry-card">
          <mat-card-header>
            <mat-card-title>
              <mat-icon class="spinning">sync</mat-icon>
              Retrying Job
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <p class="retry-message">{{ retryStatusMessage }}</p>
            <mat-progress-bar 
              [mode]="retryJobStatus === 'running' ? 'indeterminate' : 'determinate'"
              [value]="retryProgress"
              [color]="retryJobStatus === 'failed' ? 'warn' : 'primary'">
            </mat-progress-bar>
            <div class="retry-details" *ngIf="retryJobData">
              <span>New Job ID: {{ retryJobData.id }}</span>
              <span>Status: <strong>{{ retryJobData.status | uppercase }}</strong></span>
              <span *ngIf="retryJobData.tickets_processed > 0">Tickets: {{ retryJobData.tickets_processed }}</span>
            </div>
          </mat-card-content>
        </mat-card>
      </div>

      <div *ngIf="!loading && job" class="job-content">
        <!-- Summary Card -->
        <mat-card class="summary-card">
          <mat-card-header>
            <mat-card-title>Job Summary</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <div class="summary-grid">
              <div class="summary-item">
                <span class="label">Status:</span>
                <mat-chip [class]="getStatusClass(job.status)">
                  <mat-icon class="status-icon">{{ getStatusIcon(job.status) }}</mat-icon>
                  {{ job.status | uppercase }}
                </mat-chip>
              </div>
              <div class="summary-item">
                <span class="label">Triggered By:</span>
                <span>{{ job.triggered_by | titlecase }}</span>
              </div>
              <div class="summary-item">
                <span class="label">Created:</span>
                <span>{{ formatDate(job.created_at) }}</span>
              </div>
              <div class="summary-item" *ngIf="job.started_at">
                <span class="label">Started:</span>
                <span>{{ formatDate(job.started_at) }}</span>
              </div>
              <div class="summary-item" *ngIf="job.completed_at">
                <span class="label">Completed:</span>
                <span>{{ formatDate(job.completed_at) }}</span>
              </div>
              <div class="summary-item">
                <span class="label">Duration:</span>
                <span>{{ calculateDuration() }}</span>
              </div>
              <div class="summary-item">
                <span class="label">Tickets Processed:</span>
                <span class="ticket-count">{{ job.tickets_processed || 0 }}<span *ngIf="job.max_tickets"> / {{ job.max_tickets }}</span></span>
              </div>
              <div class="summary-item" *ngIf="aiCredential">
                <span class="label">AI Model:</span>
                <mat-chip class="ai-chip">
                  <mat-icon class="chip-icon">smart_toy</mat-icon>
                  {{ aiCredential.name }}
                </mat-chip>
              </div>
              <div class="summary-item full-width">
                <span class="label">JQL Query:</span>
                <code class="jql-query">{{ job.jql_query }}</code>
              </div>
              <div class="summary-item full-width" *ngIf="job.output_filename">
                <span class="label">Output File:</span>
                <span>{{ job.output_filename }}</span>
              </div>
            </div>
          </mat-card-content>
        </mat-card>

        <!-- Error Card (if failed) -->
        <mat-card class="error-card" *ngIf="job.status === 'failed' && job.error_message">
          <mat-card-header>
            <mat-card-title>
              <mat-icon color="warn">error</mat-icon>
              Error Details
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <pre class="error-message">{{ job.error_message }}</pre>
          </mat-card-content>
        </mat-card>

        <!-- Tabs for detailed information -->
        <mat-card class="details-card">
          <mat-tab-group>
            <!-- Requests Tab -->
            <mat-tab label="Requests ({{ requests.length }})">
              <div class="tab-content">
                <div *ngIf="requests.length === 0" class="empty-state">
                  <mat-icon>http</mat-icon>
                  <p>No requests recorded yet</p>
                </div>
                
                <mat-accordion *ngIf="requests.length > 0">
                  <mat-expansion-panel *ngFor="let request of requests; let i = index" 
                                       [expanded]="i === 0">
                    <mat-expansion-panel-header>
                      <mat-panel-title>
                        <mat-chip [class]="getRequestStatusClass(request.status)" class="small-chip">
                          {{ request.status | uppercase }}
                        </mat-chip>
                        <span class="request-type">{{ formatRequestType(request.type) }}</span>
                      </mat-panel-title>
                      <mat-panel-description>
                        {{ formatDate(request.timestamp) }}
                        <span class="duration" *ngIf="request.duration_ms">
                          ({{ request.duration_ms }}ms)
                        </span>
                      </mat-panel-description>
                    </mat-expansion-panel-header>
                    
                    <div class="request-details">
                      <div class="request-section">
                        <h4>Request</h4>
                        <pre class="code-block">{{ formatJson(request.request_data) }}</pre>
                      </div>
                      
                      <mat-divider></mat-divider>
                      
                      <div class="request-section" *ngIf="request.response_data">
                        <h4>Response</h4>
                        <pre class="code-block">{{ formatJson(request.response_data) }}</pre>
                      </div>
                      
                      <div class="request-section" *ngIf="request.error_message">
                        <h4>Error</h4>
                        <pre class="error-block">{{ request.error_message }}</pre>
                      </div>
                    </div>
                  </mat-expansion-panel>
                </mat-accordion>
              </div>
            </mat-tab>

            <!-- Logs Tab -->
            <mat-tab label="Logs ({{ logs.length }})">
              <div class="tab-content">
                <div *ngIf="logs.length === 0" class="empty-state">
                  <mat-icon>description</mat-icon>
                  <p>No logs available</p>
                </div>
                
                <div class="logs-container" *ngIf="logs.length > 0">
                  <div *ngFor="let log of logs" class="log-entry" [class]="'log-' + log.level">
                    <span class="log-timestamp">{{ formatTimestamp(log.timestamp) }}</span>
                    <mat-chip class="log-level" [class]="'level-' + log.level">
                      {{ log.level | uppercase }}
                    </mat-chip>
                    <span class="log-message">{{ log.message }}</span>
                    <pre *ngIf="log.details" class="log-details">{{ formatJson(log.details) }}</pre>
                  </div>
                </div>
              </div>
            </mat-tab>

            <!-- Generated Content Tab -->
            <mat-tab label="Generated Content" *ngIf="artifacts.length > 0">
              <div class="tab-content">
                <div class="artifacts-header">
                  <h3>Generated Files</h3>
                  <button mat-raised-button color="warn" (click)="clearAllArtifacts()" *ngIf="artifacts.length > 0">
                    <mat-icon>delete_sweep</mat-icon>
                    Clear All Content
                  </button>
                </div>
                <div class="artifacts-list">
                  <div *ngFor="let artifact of artifacts" class="artifact-item">
                    <mat-icon>insert_drive_file</mat-icon>
                    <div class="artifact-info">
                      <span class="artifact-name">{{ artifact.filename }}</span>
                      <span class="artifact-meta">
                        {{ formatFileSize(artifact.size_bytes) }} • 
                        {{ artifact.content_type }} • 
                        {{ formatDate(artifact.created_at) }}
                      </span>
                    </div>
                    <button mat-icon-button (click)="viewArtifact(artifact)" matTooltip="View">
                      <mat-icon>visibility</mat-icon>
                    </button>
                    <button mat-icon-button (click)="downloadSpecificArtifact(artifact)" matTooltip="Download">
                      <mat-icon>download</mat-icon>
                    </button>
                    <button mat-icon-button color="warn" (click)="deleteArtifact(artifact)" matTooltip="Delete">
                      <mat-icon>delete</mat-icon>
                    </button>
                  </div>
                </div>
                
                <div class="content-preview" *ngIf="contentPreview">
                  <h4>Content Preview</h4>
                  <pre class="code-block">{{ contentPreview }}</pre>
                </div>
              </div>
            </mat-tab>

            <!-- Metrics Tab -->
            <mat-tab label="Metrics" *ngIf="job.status === 'completed'">
              <div class="tab-content">
                <div class="metrics-grid">
                  <mat-card class="metric-card">
                    <mat-card-content>
                      <mat-icon>timer</mat-icon>
                      <div class="metric-value">{{ calculateDuration() }}</div>
                      <div class="metric-label">Total Duration</div>
                    </mat-card-content>
                  </mat-card>
                  
                  <mat-card class="metric-card">
                    <mat-card-content>
                      <mat-icon>confirmation_number</mat-icon>
                      <div class="metric-value">{{ job.tickets_processed || 0 }}</div>
                      <div class="metric-label">Tickets Processed</div>
                    </mat-card-content>
                  </mat-card>
                  
                  <mat-card class="metric-card">
                    <mat-card-content>
                      <mat-icon>http</mat-icon>
                      <div class="metric-value">{{ requests.length }}</div>
                      <div class="metric-label">API Requests</div>
                    </mat-card-content>
                  </mat-card>
                  
                  <mat-card class="metric-card">
                    <mat-card-content>
                      <mat-icon>storage</mat-icon>
                      <div class="metric-value">{{ calculateTotalSize() }}</div>
                      <div class="metric-label">Output Size</div>
                    </mat-card-content>
                  </mat-card>
                </div>
              </div>
            </mat-tab>
          </mat-tab-group>
        </mat-card>
      </div>
    </div>
  `,
  styles: [`
    .job-detail-container{max-width:1400px;margin:0 auto;padding:20px}
    .header{display:flex;align-items:center;gap:20px;margin-bottom:30px}
    .header-content{flex:1}
    .header-content h1{margin:0}
    .job-id{color:#666;font-size:14px;margin:5px 0 0 0;font-family:monospace}
    .header-actions{display:flex;gap:10px}
    .loading-container{display:flex;flex-direction:column;align-items:center;padding:60px}
    .loading-container p{margin-top:20px;color:#666}
    .job-content{display:flex;flex-direction:column;gap:20px}
    .summary-card{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white}
    .summary-card mat-card-title{color:white}
    .summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px;margin-top:20px}
    .summary-item{display:flex;flex-direction:column;gap:8px}
    .summary-item.full-width{grid-column:1/-1}
    .summary-item .label{font-weight:500;opacity:0.9;font-size:14px}
    .ticket-count{background:rgba(255,255,255,0.2);padding:4px 12px;border-radius:12px;display:inline-block;font-weight:500}
    .jql-query{background:rgba(0,0,0,0.1);padding:8px 12px;border-radius:4px;font-family:monospace;display:inline-block}
    .error-card{background:#fff3e0;border-left:4px solid #ff9800}
    .error-card mat-card-title{display:flex;align-items:center;gap:10px;color:#ff6f00}
    .error-message{background:#fff;padding:15px;border-radius:4px;border:1px solid #ffe0b2;white-space:pre-wrap;word-wrap:break-word;margin:0;font-family:monospace;font-size:13px}
    .details-card{min-height:500px}
    .tab-content{padding:20px;min-height:400px}
    .empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px;color:#999}
    .empty-state mat-icon{font-size:48px;width:48px;height:48px;margin-bottom:10px}
    mat-chip{font-size:12px}
    mat-chip.pending{background-color:#ffc107!important;color:white}
    mat-chip.running{background-color:#2196f3!important;color:white}
    mat-chip.completed{background-color:#4caf50!important;color:white}
    mat-chip.failed{background-color:#f44336!important;color:white}
    .status-icon{font-size:16px;width:16px;height:16px;margin-right:4px}
    .ai-chip{background:rgba(255,255,255,0.2)!important;color:white}
    .chip-icon{font-size:16px;width:16px;height:16px;margin-right:4px}
    .small-chip{height:20px;font-size:11px;margin-right:10px}
    .request-type{font-weight:500}
    .duration{color:#666;font-size:12px;margin-left:10px}
    .request-details{padding:20px}
    .request-section{margin:20px 0}
    .request-section h4{color:#333;margin-bottom:10px}
    .code-block{background:#f5f5f5;border:1px solid #ddd;border-radius:4px;padding:15px;font-family:monospace;font-size:12px;white-space:pre-wrap;word-wrap:break-word;max-height:400px;overflow-y:auto}
    .error-block{background:#ffebee;border:1px solid #ffcdd2;border-radius:4px;padding:15px;color:#c62828;font-family:monospace;font-size:12px;white-space:pre-wrap}
    .logs-container{max-height:600px;overflow-y:auto}
    .log-entry{padding:10px;border-bottom:1px solid #eee;display:flex;align-items:flex-start;gap:10px}
    .log-entry.log-error{background:#ffebee}
    .log-entry.log-warning{background:#fff8e1}
    .log-timestamp{font-family:monospace;font-size:12px;color:#666;white-space:nowrap}
    .log-level{height:18px;font-size:10px}
    .level-info{background:#e3f2fd!important;color:#1976d2!important}
    .level-warning{background:#fff3e0!important;color:#f57c00!important}
    .level-error{background:#ffebee!important;color:#c62828!important}
    .level-debug{background:#f5f5f5!important;color:#616161!important}
    .log-message{flex:1;font-size:14px}
    .log-details{background:rgba(0,0,0,0.05);padding:10px;border-radius:4px;margin-top:10px;font-size:12px;font-family:monospace}
    .artifacts-list{display:flex;flex-direction:column;gap:10px;margin-bottom:30px}
    .artifact-item{display:flex;align-items:center;gap:15px;padding:15px;background:#f5f5f5;border-radius:8px}
    .artifact-info{flex:1;display:flex;flex-direction:column;gap:5px}
    .artifact-name{font-weight:500}
    .artifact-meta{font-size:12px;color:#666}
    .content-preview{margin-top:30px}
    .metrics-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px}
    .metric-card{text-align:center;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white}
    .metric-card mat-icon{font-size:36px;width:36px;height:36px;margin:0 auto 10px;opacity:0.8}
    .metric-value{font-size:32px;font-weight:bold;margin:10px 0}
    .metric-label{font-size:14px;opacity:0.9}
    .request-success{background:#4caf50!important;color:white}
    .request-failed{background:#f44336!important;color:white}
    .request-pending{background:#ff9800!important;color:white}
    .artifacts-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
    .artifacts-header h3{margin:0;color:#333}
    .retry-progress-container{margin:20px 0;animation:slideDown 0.3s ease-out}
    .retry-card{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white}
    .retry-card mat-card-title{color:white;display:flex;align-items:center;gap:10px}
    .retry-card .spinning{animation:spin 2s linear infinite}
    @keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
    @keyframes slideDown{from{opacity:0;transform:translateY(-20px)}to{opacity:1;transform:translateY(0)}}
    .retry-message{margin:10px 0;font-size:16px;font-weight:500}
    .retry-details{display:flex;gap:20px;margin-top:15px;font-size:14px;opacity:0.9}
    .retry-details strong{font-weight:600}
    ::ng-deep .success-snackbar{background:#4caf50!important}
    ::ng-deep .error-snackbar{background:#f44336!important}
  `]
})
export class JobDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private jobsService = inject(JobsService);
  private credentialsService = inject(CredentialsService);
  private snackBar = inject(MatSnackBar);

  jobId: string | null = null;
  job: Job | null = null;
  loading = true;
  aiCredential: AICredential | null = null;
  
  logs: JobLog[] = [];
  requests: JobRequest[] = [];
  artifacts: JobArtifact[] = [];
  contentPreview: string | null = null;

  // Retry progress tracking
  retryInProgress = false;
  retryJobData: Job | null = null;
  retryJobStatus = '';
  retryProgress = 0;
  retryStatusMessage = 'Initializing retry...';

  private refreshSubscription?: Subscription;
  private retrySubscription?: Subscription;

  ngOnInit() {
    this.jobId = this.route.snapshot.paramMap.get('id');
    if (this.jobId) {
      this.loadJobDetails();
      
      // Auto-refresh every 5 seconds if job is running
      this.refreshSubscription = interval(5000)
        .pipe(
          startWith(0),
          switchMap(() => this.jobsService.getJob(this.jobId!))
        )
        .subscribe({
          next: (job) => {
            this.job = job;
            if (job.status === 'completed' || job.status === 'failed') {
              // Stop refreshing once job is done
              this.refreshSubscription?.unsubscribe();
            }
          },
          error: (error) => {
            console.error('Failed to refresh job:', error);
          }
        });
    } else {
      this.router.navigate(['/jobs']);
    }
  }

  ngOnDestroy() {
    this.refreshSubscription?.unsubscribe();
    this.retrySubscription?.unsubscribe();
  }

  loadJobDetails() {
    if (!this.jobId) return;

    this.loading = true;
    this.jobsService.getJob(this.jobId).subscribe({
      next: (job) => {
        this.job = job;
        this.loadAdditionalData();
        // Load AI credential details if specified
        if (job.ai_credential_id) {
          this.loadAICredential(job.ai_credential_id);
        }
      },
      error: (error) => {
        console.error('Failed to load job:', error);
        this.snackBar.open('Failed to load job details', 'Close', {
          duration: 3000
        });
        this.router.navigate(['/jobs']);
      }
    });
  }

  loadAICredential(credentialId: string) {
    this.credentialsService.getAICredentials().subscribe({
      next: (credentials) => {
        this.aiCredential = credentials.find(c => c.id === credentialId) || null;
      },
      error: (error) => {
        console.error('Failed to load AI credential details:', error);
      }
    });
  }

  loadAdditionalData() {
    if (!this.jobId) return;

    // Load artifacts
    this.jobsService.getJobArtifacts(this.jobId).subscribe({
      next: (artifacts) => {
        this.artifacts = artifacts;
      },
      error: (error) => {
        console.error('Failed to load artifacts:', error);
      }
    });

    // Load job requests from backend
    this.jobsService.getJobRequests(this.jobId).subscribe({
      next: (requests) => {
        this.requests = requests;
      },
      error: (error) => {
        console.error('Failed to load job requests:', error);
        // Fall back to mock data if requests endpoint fails
        this.loadMockRequests();
      }
    });

    // Load logs (still using mock data for now)
    this.loadMockLogs();
    
    this.loading = false;
  }

  loadMockLogs() {
    // Mock logs for now - will be replaced with real logs API later
    this.logs = [
      {
        timestamp: new Date().toISOString(),
        level: 'info',
        message: 'Job started'
      },
      {
        timestamp: new Date().toISOString(),
        level: 'info',
        message: 'Fetching tickets from JIRA',
        details: { query: this.job?.jql_query }
      },
      {
        timestamp: new Date().toISOString(),
        level: 'info',
        message: `Found ${this.job?.tickets_processed || 0} tickets`
      }
    ];

    if (this.job?.status === 'completed') {
      this.logs.push({
        timestamp: new Date().toISOString(),
        level: 'info',
        message: 'Release notes generated successfully'
      });
    } else if (this.job?.status === 'failed') {
      this.logs.push({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: 'Job failed',
        details: { error: this.job.error_message }
      });
    }
  }

  loadMockRequests() {
    // Fallback mock requests if API fails
    this.requests = [
      {
        id: '1',
        timestamp: new Date().toISOString(),
        type: 'jira_query',
        request_data: {
          method: 'POST',
          url: '/rest/api/3/search/jql',
          body: {
            jql: this.job?.jql_query,
            maxResults: 100,
            fields: ['summary', 'description', 'status', 'issuetype']
          }
        },
        response_data: {
          total: this.job?.tickets_processed || 0,
          issues: []
        },
        status: 'success',
        duration_ms: 245
      }
    ];

    if (this.job?.status === 'completed') {
      this.requests.push({
        id: '2',
        timestamp: new Date().toISOString(),
        type: 'ai_generation',
        request_data: {
          model: 'gpt-4',
          prompt: 'Generate release notes...',
          tickets: this.job?.tickets_processed || 0
        },
        response_data: {
          content: 'Generated release notes content...'
        },
        status: 'success',
        duration_ms: 3250
      });
    }
  }

  navigateBack() {
    this.router.navigate(['/jobs']);
  }

  downloadArtifact() {
    if (!this.job?.id || this.artifacts.length === 0) return;
    
    const artifact = this.artifacts[0];
    this.jobsService.downloadArtifact(this.job.id, artifact.id).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = artifact.filename;
        a.click();
        window.URL.revokeObjectURL(url);
        
        this.snackBar.open('Download started', 'Close', {
          duration: 3000
        });
      },
      error: (error) => {
        this.snackBar.open('Failed to download artifact', 'Close', {
          duration: 3000
        });
      }
    });
  }

  downloadSpecificArtifact(artifact: JobArtifact) {
    if (!this.job?.id) return;
    
    this.jobsService.downloadArtifact(this.job.id, artifact.id).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = artifact.filename;
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: (error) => {
        this.snackBar.open('Failed to download artifact', 'Close', {
          duration: 3000
        });
      }
    });
  }

  viewArtifact(artifact: JobArtifact) {
    if (!this.job?.id) return;
    
    // Fetch the actual content
    this.jobsService.getArtifactContent(this.job.id, artifact.id).subscribe({
      next: (response) => {
        this.contentPreview = response.content;
      },
      error: (error) => {
        console.error('Failed to load artifact content:', error);
        this.snackBar.open('Failed to load artifact content', 'Close', {
          duration: 3000
        });
      }
    });
  }

  retryJob() {
    if (!this.job?.id) return;
    
    // Start retry progress tracking
    this.retryInProgress = true;
    this.retryProgress = 0;
    this.retryStatusMessage = 'Creating retry job...';
    
    this.jobsService.retryJob(this.job.id).subscribe({
      next: (newJob) => {
        // Clear the error from the current job display since we're retrying
        // Keep status as 'failed' but clear the error message for visual feedback
        if (this.job) {
          this.job.error_message = undefined;
          // Note: We keep status as 'failed' since 'retrying' is not a valid status
          // The retry progress bar will show that a retry is in progress
        }
        
        this.retryJobData = newJob;
        this.retryJobStatus = newJob.status;
        this.retryProgress = 10;
        this.retryStatusMessage = 'Retry job created. Starting execution...';
        
        // Start monitoring the new job
        this.monitorRetryJob(newJob.id);
        
        this.snackBar.open('Job retry initiated', 'Close', {
          duration: 3000
        });
      },
      error: (error) => {
        this.retryInProgress = false;
        this.snackBar.open('Failed to retry job', 'Close', {
          duration: 3000
        });
      }
    });
  }

  private monitorRetryJob(jobId: string) {
    // Poll the retry job status every 2 seconds
    this.retrySubscription = interval(2000)
      .pipe(
        startWith(0),
        switchMap(() => this.jobsService.getJob(jobId))
      )
      .subscribe({
        next: (job) => {
          this.retryJobData = job;
          this.retryJobStatus = job.status;
          
          // Update progress and message based on status
          switch (job.status) {
            case 'pending':
              this.retryProgress = 20;
              this.retryStatusMessage = 'Job queued for processing...';
              break;
            case 'running':
              // For running jobs, estimate progress based on tickets processed
              if (job.tickets_processed > 0 && this.job?.tickets_processed) {
                const percentComplete = (job.tickets_processed / this.job.tickets_processed) * 60 + 30;
                this.retryProgress = Math.min(percentComplete, 90);
                this.retryStatusMessage = `Processing tickets... (${job.tickets_processed} processed)`;
              } else {
                this.retryProgress = 30;
                this.retryStatusMessage = 'Processing release notes...';
              }
              break;
            case 'completed':
              this.retryProgress = 100;
              this.retryStatusMessage = 'Job completed successfully!';
              this.handleRetryComplete(job);
              break;
            case 'failed':
              this.retryProgress = 100;
              this.retryStatusMessage = `Job failed: ${job.error_message || 'Unknown error'}`;
              this.handleRetryFailed(job);
              break;
          }
        },
        error: (error) => {
          console.error('Error monitoring retry job:', error);
          this.retryInProgress = false;
          this.retrySubscription?.unsubscribe();
        }
      });
  }

  private handleRetryComplete(newJob: Job) {
    // Stop monitoring
    this.retrySubscription?.unsubscribe();
    
    // Show success for 2 seconds then navigate to new job
    setTimeout(() => {
      this.retryInProgress = false;
      // Replace current job with the new one
      this.job = newJob;
      this.jobId = newJob.id;
      // Update the URL without full navigation
      window.history.replaceState({}, '', `/jobs/${newJob.id}`);
      // Reload job details
      this.loadJobDetails();
      
      this.snackBar.open('Job retry completed successfully!', 'Close', {
        duration: 5000,
        panelClass: ['success-snackbar']
      });
    }, 2000);
  }

  private handleRetryFailed(newJob: Job) {
    // Stop monitoring
    this.retrySubscription?.unsubscribe();
    
    // Update the original job display with the new failure info
    if (this.job) {
      this.job.status = 'failed';
      this.job.error_message = newJob.error_message;
      this.job.completed_at = newJob.completed_at;
    }
    
    // Show error for 3 seconds then hide progress
    setTimeout(() => {
      this.retryInProgress = false;
      
      // Replace current job with the failed retry so we have the latest error
      this.job = newJob;
      this.jobId = newJob.id;
      // Update the URL to the new job
      window.history.replaceState({}, '', `/jobs/${newJob.id}`);
      // Reload job details to get the latest data
      this.loadJobDetails();
      
      this.snackBar.open(`Retry failed: ${newJob.error_message || 'Unknown error'}`, 'Close', {
        duration: 5000,
        panelClass: ['error-snackbar']
      });
    }, 3000);
  }

  cancelJob() {
    if (!this.job?.id) return;
    
    if (confirm('Are you sure you want to cancel this job?')) {
      this.jobsService.cancelJob(this.job.id).subscribe({
        next: () => {
          this.job!.status = 'failed';
          this.snackBar.open('Job cancelled', 'Close', {
            duration: 3000
          });
        },
        error: (error) => {
          this.snackBar.open('Failed to cancel job', 'Close', {
            duration: 3000
          });
        }
      });
    }
  }

  getStatusClass(status: string): string {
    return status.toLowerCase();
  }

  getStatusIcon(status: string): string {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'schedule';
      case 'running':
        return 'sync';
      case 'completed':
        return 'check_circle';
      case 'failed':
        return 'error';
      default:
        return 'help';
    }
  }

  getRequestStatusClass(status: string): string {
    return `request-${status}`;
  }

  formatRequestType(type: string): string {
    const typeMap: { [key: string]: string } = {
      'jira_query': 'JIRA Query',
      'ai_generation': 'AI Generation',
      'heretto_publish': 'Heretto Publish'
    };
    return typeMap[type] || type;
  }

  formatDate(dateStr: string): string {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  }

  formatTimestamp(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  }

  formatJson(obj: any): string {
    if (!obj) return '';
    if (typeof obj === 'string') return obj;
    return JSON.stringify(obj, null, 2);
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  }

  calculateDuration(): string {
    if (!this.job?.started_at) return 'N/A';
    
    const start = new Date(this.job.started_at);
    const end = this.job.completed_at ? new Date(this.job.completed_at) : new Date();
    const duration = end.getTime() - start.getTime();
    
    const seconds = Math.floor(duration / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  }

  calculateTotalSize(): string {
    const totalBytes = this.artifacts.reduce((sum, a) => sum + a.size_bytes, 0);
    return this.formatFileSize(totalBytes);
  }

  deleteArtifact(artifact: JobArtifact) {
    if (!this.job?.id) return;
    
    const confirmMessage = `Are you sure you want to delete "${artifact.filename}"? This action cannot be undone.`;
    
    if (confirm(confirmMessage)) {
      this.jobsService.deleteArtifact(this.job.id, artifact.id).subscribe({
        next: (response) => {
          // Remove artifact from local array
          this.artifacts = this.artifacts.filter(a => a.id !== artifact.id);
          
          // Clear preview if this artifact was being viewed
          if (this.contentPreview) {
            this.contentPreview = null;
          }
          
          this.snackBar.open(`Deleted ${artifact.filename}`, 'Close', {
            duration: 3000,
            panelClass: ['success-snackbar']
          });
        },
        error: (error) => {
          console.error('Failed to delete artifact:', error);
          this.snackBar.open('Failed to delete artifact', 'Close', {
            duration: 3000,
            panelClass: ['error-snackbar']
          });
        }
      });
    }
  }

  clearAllArtifacts() {
    if (!this.job?.id) return;
    
    const confirmMessage = `Are you sure you want to delete ALL generated content for this job? This will permanently delete ${this.artifacts.length} file(s) and cannot be undone.`;
    
    if (confirm(confirmMessage)) {
      const doubleConfirm = prompt('Type "DELETE" to confirm deletion of all artifacts:');
      
      if (doubleConfirm === 'DELETE') {
        this.jobsService.deleteAllArtifacts(this.job.id).subscribe({
          next: (response) => {
            const deletedCount = response.deleted_count || this.artifacts.length;
            
            // Clear local artifacts array
            this.artifacts = [];
            this.contentPreview = null;
            
            this.snackBar.open(`Successfully deleted ${deletedCount} artifact(s)`, 'Close', {
              duration: 3000,
              panelClass: ['success-snackbar']
            });
          },
          error: (error) => {
            console.error('Failed to delete artifacts:', error);
            this.snackBar.open('Failed to delete artifacts', 'Close', {
              duration: 3000,
              panelClass: ['error-snackbar']
            });
          }
        });
      } else {
        this.snackBar.open('Deletion cancelled', 'Close', {
          duration: 2000
        });
      }
    }
  }
}