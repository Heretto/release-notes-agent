import { Component, OnInit, OnDestroy, inject, ChangeDetectionStrategy } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';
import { interval, Subscription } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';
import { JobsService, Job, JOB_STAGES } from '../../core/services/jobs.service';
import { InstructionsService } from '../../core/services/instructions.service';
import { JobCreateDialogComponent } from '../jobs/job-create-dialog.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    DatePipe,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatDialogModule,
    MatSnackBarModule,
    RouterLink
  ],
  template: `
    <div class="hop-page">
      <div class="header">
        <div>
          <h1>Dashboard</h1>
          <p class="subtitle">Releases in progress and what is waiting on you</p>
        </div>
        <button mat-raised-button color="primary" (click)="startRelease()">
          <mat-icon>rocket_launch</mat-icon>
          Start a release
        </button>
      </div>

      <div class="stats-grid">
        <mat-card class="hop-stat-card">
          <span class="hop-icon-badge"><mat-icon>work</mat-icon></span>
          <div>
            <span class="hop-stat-value">{{ totalJobs }}</span>
            <span class="hop-stat-label">Releases</span>
          </div>
        </mat-card>
        <mat-card class="hop-stat-card">
          <span class="hop-icon-badge accent"><mat-icon>rate_review</mat-icon></span>
          <div>
            <span class="hop-stat-value">{{ notesToReview }}</span>
            <span class="hop-stat-label">Notes to review</span>
          </div>
        </mat-card>
        <mat-card class="hop-stat-card">
          <span class="hop-icon-badge warning"><mat-icon>flag</mat-icon></span>
          <div>
            <span class="hop-stat-value">{{ notesNeedingAttention }}</span>
            <span class="hop-stat-label">Need attention</span>
          </div>
        </mat-card>
        <mat-card class="hop-stat-card">
          <span class="hop-icon-badge" [class.info]="runningJobs > 0" [class.error]="runningJobs === 0 && failedJobs > 0" [class.success]="runningJobs === 0 && failedJobs === 0">
            <mat-icon>{{ runningJobs > 0 ? 'sync' : (failedJobs > 0 ? 'error' : 'check_circle') }}</mat-icon>
          </span>
          <div>
            <span class="hop-stat-value">{{ runningJobs > 0 ? runningJobs : failedJobs }}</span>
            <span class="hop-stat-label">{{ runningJobs > 0 ? 'Running' : 'Failed' }}</span>
          </div>
        </mat-card>
      </div>

      <mat-card class="recent-jobs">
        <div class="card-head">
          <h2>Recent releases</h2>
          <a mat-button routerLink="/jobs">All releases</a>
        </div>
        @if (recentJobs.length === 0) {
          <p class="no-data">No releases yet. Start one from an instruction set.</p>
        }
        @if (recentJobs.length > 0) {
          <table class="jobs-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Release</th>
                <th>Progress</th>
                <th>Notes</th>
                <th>Updated</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (job of recentJobs; track job.id) {
                <tr [class.hop-shimmer]="job.status === 'running'">
                  <td><span [class]="'hop-status-chip hop-status-chip-' + chipClass(job)">{{ statusLabel(job) }}</span></td>
                  <td>
                    <a [routerLink]="['/jobs', job.id]" class="release-link">{{ job.title || job.output_filename || 'Untitled' }}</a>
                  </td>
                  <td class="muted">{{ progressText(job) }}</td>
                  <td>
                    @if (job.counts) {
                      {{ job.counts.approved_items }}/{{ job.counts.items }} approved
                      @if (job.counts.attention_items) { <span class="attention">· {{ job.counts.attention_items }} flagged</span> }
                    }
                  </td>
                  <td class="muted">{{ (job.completed_at || job.started_at || job.created_at) | date:'short' }}</td>
                  <td class="row-actions">
                    @if (job.status === 'completed') {
                      <a mat-stroked-button [routerLink]="['/jobs', job.id, 'workspace']">
                        <mat-icon>edit_note</mat-icon> Workspace
                      </a>
                    } @else {
                      <a mat-button [routerLink]="['/jobs', job.id]">Details</a>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>
        }
      </mat-card>

      <div class="actions-section">
        <h2>Set up</h2>
        <div class="action-buttons">
          <button mat-stroked-button routerLink="/instructions">
            <mat-icon>description</mat-icon>
            Instruction sets
          </button>
          <button mat-stroked-button routerLink="/agents">
            <mat-icon>smart_toy</mat-icon>
            Agents
          </button>
          <button mat-stroked-button routerLink="/credentials">
            <mat-icon>vpn_key</mat-icon>
            Credentials
          </button>
        </div>
      </div>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; gap: 16px; flex-wrap: wrap; }
    .header h1 { margin: 0; }
    .subtitle { color: var(--text-secondary); margin: 5px 0 0 0; }
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 28px; }
    .recent-jobs { padding: 20px 24px; margin-bottom: 28px; }
    .card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .card-head h2 { margin: 0; font-size: 18px; }
    .no-data { text-align: center; color: var(--text-tertiary); padding: 32px 0; }
    .jobs-table { width: 100%; border-collapse: collapse; }
    .jobs-table th, .jobs-table td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border-default); vertical-align: middle; }
    .jobs-table th { color: var(--text-tertiary); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
    .jobs-table tbody tr:last-child td { border-bottom: none; }
    .release-link { color: var(--text-primary); text-decoration: none; font-weight: 500; }
    .release-link:hover { text-decoration: underline; }
    .muted { color: var(--text-secondary); font-size: 13px; }
    .attention { color: var(--color-warning-text); }
    .row-actions { text-align: right; white-space: nowrap; }
    .actions-section h2 { font-size: 18px; margin-bottom: 12px; }
    .action-buttons { display: flex; gap: 12px; flex-wrap: wrap; }
  `]
})
export class DashboardComponent implements OnInit, OnDestroy {
  private jobsService = inject(JobsService);
  private instructionsService = inject(InstructionsService);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);
  private router = inject(Router);

  totalJobs = 0;
  runningJobs = 0;
  failedJobs = 0;
  notesToReview = 0;
  notesNeedingAttention = 0;
  recentJobs: Job[] = [];

  private refresh?: Subscription;

  ngOnInit(): void {
    this.refresh = interval(10000).pipe(
      startWith(0),
      switchMap(() => this.jobsService.getJobs())
    ).subscribe({
      next: (jobs) => {
        this.totalJobs = jobs.length;
        this.runningJobs = jobs.filter(j => j.status === 'running' || j.status === 'pending').length;
        this.failedJobs = jobs.filter(j => j.status === 'failed').length;
        const completed = jobs.filter(j => j.status === 'completed' && j.counts);
        this.notesToReview = completed.reduce((sum, j) => sum + (j.counts!.items - j.counts!.approved_items), 0);
        this.notesNeedingAttention = completed.reduce((sum, j) => sum + j.counts!.attention_items, 0);
        this.recentJobs = jobs.slice(0, 6);
      }
    });
  }

  ngOnDestroy(): void {
    this.refresh?.unsubscribe();
  }

  chipClass(job: Job): string {
    return job.status === 'cancelled' ? 'failed' : job.status;
  }

  statusLabel(job: Job): string {
    if (job.status === 'completed') return 'Ready';
    return job.status.charAt(0).toUpperCase() + job.status.slice(1);
  }

  progressText(job: Job): string {
    if (job.status === 'running' && job.stage) {
      const stage = JOB_STAGES.find(s => s.key === job.stage);
      return `${stage?.label || job.stage}${job.stage_message ? ' — ' + job.stage_message : ''}`;
    }
    if (job.status === 'failed') return job.error_message || 'Failed';
    return job.stage_message || '';
  }

  startRelease(): void {
    this.instructionsService.getInstructionSets().subscribe(instructionSets => {
      if (instructionSets.length === 0) {
        this.snackBar.open('Create an instruction set first', 'Go', { duration: 5000 })
          .onAction().subscribe(() => this.router.navigate(['/instructions']));
        return;
      }
      const ref = this.dialog.open(JobCreateDialogComponent, { width: '640px', data: { instructionSets } });
      ref.afterClosed().subscribe(jobData => {
        if (!jobData) return;
        this.jobsService.createJob(jobData).subscribe({
          next: (job) => this.router.navigate(['/jobs', job.id]),
          error: (error) => this.snackBar.open(error.error?.detail || 'Failed to start the release', 'Close', { duration: 5000 })
        });
      });
    });
  }
}
