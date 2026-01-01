import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatMenuModule } from '@angular/material/menu';
import { JobsService, Job } from '../../core/services/jobs.service';
import { InstructionsService, InstructionSet } from '../../core/services/instructions.service';
import { JobCreateDialogComponent } from './job-create-dialog.component';
import { interval, Subscription } from 'rxjs';
import { switchMap, startWith } from 'rxjs/operators';

@Component({
  selector: 'app-jobs',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTableModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatDialogModule,
    MatSnackBarModule,
    MatMenuModule
  ],
  template: `
    <div class="jobs-container">
      <div class="header">
        <div>
          <h1>Jobs</h1>
          <p class="subtitle">Monitor and manage release note generation jobs</p>
        </div>
        <button mat-raised-button color="primary" (click)="createJob()">
          <mat-icon>add</mat-icon>
          Create New Job
        </button>
      </div>
      
      <div *ngIf="loading" class="loading-container">
        <mat-spinner></mat-spinner>
        <p>Loading jobs...</p>
      </div>

      <div *ngIf="!loading && jobs.length === 0" class="empty-state">
        <mat-card>
          <mat-card-content>
            <mat-icon class="empty-icon">work_off</mat-icon>
            <h3>No Jobs Yet</h3>
            <p>Create your first job to start generating release notes.</p>
            <button mat-raised-button color="primary" (click)="createJob()">
              <mat-icon>add</mat-icon>
              Create Your First Job
            </button>
          </mat-card-content>
        </mat-card>
      </div>

      <div *ngIf="!loading && jobs.length > 0" class="jobs-list">
        <mat-card class="jobs-table-card">
          <table mat-table [dataSource]="jobs" class="jobs-table">
            
            <!-- Status Column -->
            <ng-container matColumnDef="status">
              <th mat-header-cell *matHeaderCellDef>Status</th>
              <td mat-cell *matCellDef="let job">
                <mat-chip [class]="getStatusClass(job.status)">
                  <mat-icon class="status-icon">{{ getStatusIcon(job.status) }}</mat-icon>
                  {{ job.status | uppercase }}
                </mat-chip>
              </td>
            </ng-container>

            <!-- JQL Query Column -->
            <ng-container matColumnDef="jql_query">
              <th mat-header-cell *matHeaderCellDef>JQL Query</th>
              <td mat-cell *matCellDef="let job" class="query-cell">
                <span [matTooltip]="job.jql_query">
                  {{ truncateQuery(job.jql_query) }}
                </span>
              </td>
            </ng-container>

            <!-- Output Column -->
            <ng-container matColumnDef="output_filename">
              <th mat-header-cell *matHeaderCellDef>Output</th>
              <td mat-cell *matCellDef="let job">
                {{ job.output_filename || 'N/A' }}
              </td>
            </ng-container>

            <!-- Tickets Column -->
            <ng-container matColumnDef="tickets_processed">
              <th mat-header-cell *matHeaderCellDef>Tickets</th>
              <td mat-cell *matCellDef="let job">
                <span class="ticket-count">{{ job.tickets_processed || 0 }}</span>
              </td>
            </ng-container>

            <!-- Created Column -->
            <ng-container matColumnDef="created_at">
              <th mat-header-cell *matHeaderCellDef>Created</th>
              <td mat-cell *matCellDef="let job">
                {{ formatDate(job.created_at) }}
              </td>
            </ng-container>

            <!-- Duration Column -->
            <ng-container matColumnDef="duration">
              <th mat-header-cell *matHeaderCellDef>Duration</th>
              <td mat-cell *matCellDef="let job">
                {{ calculateDuration(job) }}
              </td>
            </ng-container>

            <!-- Actions Column -->
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef>Actions</th>
              <td mat-cell *matCellDef="let job">
                <button mat-icon-button [matMenuTriggerFor]="menu" (click)="$event.stopPropagation()">
                  <mat-icon>more_vert</mat-icon>
                </button>
                <mat-menu #menu="matMenu">
                  <button mat-menu-item (click)="viewJob(job)" *ngIf="job.status === 'completed'">
                    <mat-icon>visibility</mat-icon>
                    <span>View Output</span>
                  </button>
                  <button mat-menu-item (click)="downloadArtifact(job)" *ngIf="job.status === 'completed'">
                    <mat-icon>download</mat-icon>
                    <span>Download</span>
                  </button>
                  <button mat-menu-item (click)="retryJob(job)" *ngIf="job.status === 'failed'">
                    <mat-icon>refresh</mat-icon>
                    <span>Retry</span>
                  </button>
                  <button mat-menu-item (click)="cancelJob(job)" 
                          *ngIf="job.status === 'running' || job.status === 'pending'">
                    <mat-icon>cancel</mat-icon>
                    <span>Cancel</span>
                  </button>
                  <button mat-menu-item (click)="viewError(job)" *ngIf="job.error_message">
                    <mat-icon>error_outline</mat-icon>
                    <span>View Error</span>
                  </button>
                </mat-menu>
              </td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: displayedColumns;" 
                [class.running-job]="row.status === 'running'"
                class="clickable-row"
                (click)="navigateToJob(row)"
                matTooltip="Click to view details"></tr>
          </table>
        </mat-card>
      </div>
    </div>
  `,
  styles: [`
    .jobs-container {
      max-width: 1400px;
      margin: 0 auto;
      padding: 20px;
    }
    
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 30px;
    }

    .header h1 {
      margin: 0;
    }

    .subtitle {
      color: #666;
      margin: 5px 0 0 0;
    }

    .loading-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 60px;
    }

    .loading-container p {
      margin-top: 20px;
      color: #666;
    }

    .empty-state {
      text-align: center;
      padding: 40px 20px;
    }

    .empty-state mat-card {
      max-width: 500px;
      margin: 0 auto;
      padding: 40px;
    }

    .empty-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #ddd;
      margin: 0 auto 20px;
    }

    .empty-state h3 {
      color: #333;
      margin-bottom: 10px;
    }

    .empty-state p {
      color: #666;
      margin-bottom: 20px;
    }

    .jobs-list {
      margin-top: 20px;
    }

    .jobs-table-card {
      overflow: hidden;
    }

    .jobs-table {
      width: 100%;
    }

    .query-cell {
      max-width: 300px;
      font-family: monospace;
      font-size: 12px;
    }

    .ticket-count {
      background: #e3f2fd;
      padding: 4px 8px;
      border-radius: 12px;
      font-weight: 500;
    }

    mat-chip {
      font-size: 12px;
      height: 24px;
      display: inline-flex;
      align-items: center;
    }

    mat-chip.pending {
      background-color: #ffc107 !important;
      color: white;
    }

    mat-chip.running {
      background-color: #2196f3 !important;
      color: white;
    }

    mat-chip.completed {
      background-color: #4caf50 !important;
      color: white;
    }

    mat-chip.failed {
      background-color: #f44336 !important;
      color: white;
    }

    .status-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
      margin-right: 4px;
    }

    .running-job {
      background: linear-gradient(90deg, 
        rgba(33, 150, 243, 0.05) 0%, 
        rgba(33, 150, 243, 0.1) 50%, 
        rgba(33, 150, 243, 0.05) 100%);
      animation: pulse 2s ease-in-out infinite;
    }

    @keyframes pulse {
      0%, 100% {
        opacity: 1;
      }
      50% {
        opacity: 0.7;
      }
    }

    .clickable-row {
      cursor: pointer !important;
      transition: background-color 0.2s;
    }

    .clickable-row:hover {
      background-color: rgba(0, 0, 0, 0.04) !important;
    }
    
    /* Make sure the entire row is clickable except for buttons */
    .clickable-row td {
      cursor: pointer !important;
    }
    
    .clickable-row button {
      cursor: pointer !important;
      position: relative;
      z-index: 1;
    }
  `]
})
export class JobsComponent implements OnInit, OnDestroy {
  private jobsService = inject(JobsService);
  private instructionsService = inject(InstructionsService);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);
  private router = inject(Router);
  
  jobs: Job[] = [];
  loading = false;
  displayedColumns = ['status', 'jql_query', 'output_filename', 'tickets_processed', 'created_at', 'duration', 'actions'];
  
  private refreshSubscription?: Subscription;

  ngOnInit() {
    this.loadJobs();
    // Auto-refresh every 5 seconds to update job statuses
    this.refreshSubscription = interval(5000)
      .pipe(
        startWith(0),
        switchMap(() => this.jobsService.getJobs())
      )
      .subscribe({
        next: (jobs) => {
          this.jobs = jobs;
        },
        error: (error) => {
          console.error('Failed to refresh jobs:', error);
        }
      });
  }

  ngOnDestroy() {
    this.refreshSubscription?.unsubscribe();
  }

  loadJobs() {
    this.loading = true;
    this.jobsService.getJobs().subscribe({
      next: (jobs) => {
        this.jobs = jobs;
        this.loading = false;
      },
      error: (error) => {
        console.error('Failed to load jobs:', error);
        this.loading = false;
        this.snackBar.open('Failed to load jobs', 'Close', {
          duration: 3000
        });
      }
    });
  }

  createJob() {
    console.log('Create job button clicked');
    
    // First, get instruction sets to select from
    this.instructionsService.getInstructionSets().subscribe({
      next: (instructions) => {
        console.log('Loaded instruction sets:', instructions);
        
        if (instructions.length === 0) {
          this.snackBar.open('Please create an instruction set first', 'Close', {
            duration: 3000
          });
          return;
        }

        // Get default or first instruction set
        const defaultInstruction = instructions.find(i => i.is_default) || instructions[0];
        console.log('Using instruction:', defaultInstruction);
        
        const dialogRef = this.dialog.open(JobCreateDialogComponent, {
          width: '600px',
          data: defaultInstruction
        });

        dialogRef.afterClosed().subscribe(jobData => {
          if (jobData) {
            this.jobsService.createJob(jobData).subscribe({
              next: (job) => {
                this.jobs.unshift(job);
                this.snackBar.open('Job created successfully!', 'Close', {
                  duration: 3000
                });
              },
              error: (error) => {
                console.error('Failed to create job:', error);
                this.snackBar.open(
                  error.error?.detail || 'Failed to create job',
                  'Close',
                  { duration: 5000 }
                );
              }
            });
          }
        });
      },
      error: (error) => {
        console.error('Failed to load instruction sets:', error);
        this.snackBar.open(
          error.status === 401 ? 'Session expired. Please log in again.' : 'Failed to load instruction sets',
          'Close',
          { duration: 5000 }
        );
      }
    });
  }

  viewJob(job: Job) {
    this.navigateToJob(job);
  }

  navigateToJob(job: Job) {
    console.log('Navigating to job:', job.id);
    if (job.id) {
      this.router.navigate(['/jobs', job.id]);
    } else {
      console.error('Job has no ID:', job);
    }
  }

  downloadArtifact(job: Job) {
    if (!job.id) return;
    
    this.jobsService.getJobArtifacts(job.id).subscribe({
      next: (artifacts) => {
        if (artifacts.length > 0) {
          const artifact = artifacts[0];
          this.jobsService.downloadArtifact(job.id, artifact.id).subscribe({
            next: (blob) => {
              const url = window.URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = job.output_filename || 'release-notes.xml';
              a.click();
              window.URL.revokeObjectURL(url);
            },
            error: (error) => {
              this.snackBar.open('Failed to download artifact', 'Close', {
                duration: 3000
              });
            }
          });
        } else {
          this.snackBar.open('No artifacts available', 'Close', {
            duration: 3000
          });
        }
      },
      error: (error) => {
        this.snackBar.open('Failed to get artifacts', 'Close', {
          duration: 3000
        });
      }
    });
  }

  retryJob(job: Job) {
    if (!job.id) return;
    
    this.jobsService.retryJob(job.id).subscribe({
      next: (newJob) => {
        this.jobs.unshift(newJob);
        this.snackBar.open('Job retry initiated', 'Close', {
          duration: 3000
        });
      },
      error: (error) => {
        this.snackBar.open('Failed to retry job', 'Close', {
          duration: 3000
        });
      }
    });
  }

  cancelJob(job: Job) {
    if (!job.id) return;
    
    if (confirm('Are you sure you want to cancel this job?')) {
      this.jobsService.cancelJob(job.id).subscribe({
        next: () => {
          job.status = 'failed';
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

  viewError(job: Job) {
    if (job.error_message) {
      alert(`Error Details:\n\n${job.error_message}`);
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

  truncateQuery(query: string): string {
    return query.length > 80 ? query.substring(0, 80) + '...' : query;
  }

  formatDate(dateStr: string): string {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  }

  calculateDuration(job: Job): string {
    if (!job.started_at) return 'N/A';
    
    const start = new Date(job.started_at);
    const end = job.completed_at ? new Date(job.completed_at) : new Date();
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
}