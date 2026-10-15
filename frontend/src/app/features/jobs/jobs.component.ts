import { Component, OnInit, OnDestroy, inject, ChangeDetectionStrategy } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatMenuModule } from '@angular/material/menu';
import { HopDataTableComponent, HopTableCellDirective, HopTableColumn, HopConfirmDialogComponent } from '@heretto/hop-ui';
import { JobsService, Job, JOB_STAGES } from '../../core/services/jobs.service';
import { InstructionsService } from '../../core/services/instructions.service';
import { JobCreateDialogComponent } from './job-create-dialog.component';
import { interval, Subscription } from 'rxjs';
import { switchMap, startWith } from 'rxjs/operators';

@Component({
  selector: 'app-jobs',
  standalone: true,
  imports: [
    DatePipe,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatDialogModule,
    MatSnackBarModule,
    MatMenuModule,
    HopDataTableComponent,
    HopTableCellDirective
  ],
  template: `
    <div class="hop-page">
      <div class="header">
        <div>
          <h1>Releases</h1>
          <p class="subtitle">Every run of the pipeline, and the workspace where its release notes are finished</p>
        </div>
        <button mat-raised-button color="primary" (click)="createJob()">
          <mat-icon>rocket_launch</mat-icon>
          Start a release
        </button>
      </div>

      @if (loading) {
        <div class="loading-container">
          <mat-spinner></mat-spinner>
          <p>Loading releases...</p>
        </div>
      }

      @if (!loading && jobs.length === 0) {
        <div class="empty-state">
          <mat-card>
            <mat-card-content>
              <mat-icon class="empty-icon">work_off</mat-icon>
              <h3>No releases yet</h3>
              <p>Start one and the agents will draft release notes from your Jira issues.</p>
              <button mat-raised-button color="primary" (click)="createJob()">
                <mat-icon>rocket_launch</mat-icon>
                Start your first release
              </button>
            </mat-card-content>
          </mat-card>
        </div>
      }

      @if (!loading && jobs.length > 0) {
        <mat-card class="table-card">
          <hop-data-table [columns]="columns" [data]="jobs" [filterable]="true"
                          filterPlaceholder="Filter releases" sortActive="created" sortDirection="desc">
            <ng-template hopCell="status" let-job>
              <span [class]="'hop-status-chip hop-status-chip-' + chipClass(job)"
                    [class.hop-shimmer]="job.status === 'running'">{{ statusLabel(job) }}</span>
            </ng-template>
            <ng-template hopCell="title" let-job>
              <a [routerLink]="['/releases', job.id]" class="release-link">{{ titleOf(job) }}</a>
              <div class="query-preview" [matTooltip]="job.jql_query">{{ job.jql_query }}</div>
            </ng-template>
            <ng-template hopCell="progress" let-job>
              <span class="progress" [class.error]="job.status === 'failed'" [matTooltip]="progressText(job)">{{ progressText(job) }}</span>
            </ng-template>
            <ng-template hopCell="notes" let-job>
              @if (job.counts && job.counts.items) {
                <span class="count-pill">{{ job.counts.approved_items }}/{{ job.counts.items }}</span>
                @if (job.counts.attention_items) {
                  <mat-icon class="attention-icon" [matTooltip]="job.counts.attention_items + ' note(s) need attention'">flag</mat-icon>
                }
              } @else {
                <span class="muted">—</span>
              }
            </ng-template>
            <ng-template hopCell="issues" let-job>
              @if (job.counts) {
                <span [matTooltip]="job.counts.relevant_issues + ' relevant of ' + job.counts.issues">
                  {{ job.counts.relevant_issues }}/{{ job.counts.issues }}
                </span>
              }
            </ng-template>
            <ng-template hopCell="created" let-job>
              {{ job.created_at | date:'short' }}
              @if (job.run_count > 1) { <div class="muted">{{ job.run_count }} runs</div> }
            </ng-template>
            <ng-template hopCell="actions" let-job>
              <div class="row-actions">
                @if (job.status === 'completed') {
                  <a mat-stroked-button [routerLink]="['/releases', job.id, 'workspace']">
                    <mat-icon>edit_note</mat-icon> Workspace
                  </a>
                }
                <button mat-icon-button [matMenuTriggerFor]="menu" (click)="$event.stopPropagation()">
                  <mat-icon>more_vert</mat-icon>
                </button>
                <mat-menu #menu="matMenu">
                  <a mat-menu-item [routerLink]="['/releases', job.id]">
                    <mat-icon>info</mat-icon><span>Details and run log</span>
                  </a>
                  @if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
                    <button mat-menu-item (click)="rerunJob(job)">
                      <mat-icon>replay</mat-icon><span>Rerun (check Jira for changes)</span>
                    </button>
                  }
                  @if (job.status === 'running' || job.status === 'pending') {
                    <button mat-menu-item (click)="cancelJob(job)">
                      <mat-icon>cancel</mat-icon><span>Cancel</span>
                    </button>
                  }
                  <button mat-menu-item (click)="deleteJob(job)">
                    <mat-icon>delete</mat-icon><span>Delete</span>
                  </button>
                </mat-menu>
              </div>
            </ng-template>
          </hop-data-table>
        </mat-card>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; gap: 16px; flex-wrap: wrap; }
    .header h1 { margin: 0; }
    .subtitle { color: var(--text-secondary); margin: 5px 0 0 0; }
    .loading-container { display: flex; flex-direction: column; align-items: center; padding: 60px; }
    .loading-container p { margin-top: 20px; color: var(--text-secondary); }
    .empty-state { text-align: center; padding: 40px 20px; }
    .empty-state mat-card { max-width: 500px; margin: 0 auto; padding: 40px; }
    .empty-icon { font-size: 64px; width: 64px; height: 64px; color: var(--border-default); margin: 0 auto 20px; }
    .empty-state h3 { color: var(--text-primary); margin-bottom: 10px; }
    .empty-state p { color: var(--text-secondary); margin-bottom: 20px; }
    .table-card { overflow: hidden; }
    .release-link { color: var(--text-primary); font-weight: 500; text-decoration: none; }
    .release-link:hover { text-decoration: underline; }
    .query-preview { font-family: var(--font-mono); font-size: 11px; color: var(--text-tertiary); max-width: 360px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .progress { display: block; font-size: 13px; color: var(--text-secondary); max-width: 320px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .progress.error { color: var(--color-error-text); }
    .count-pill { background: var(--color-primary-bg); padding: 2px 8px; border-radius: 12px; font-weight: 500; font-size: 13px; }
    .attention-icon { font-size: 18px; width: 18px; height: 18px; color: var(--color-warning); vertical-align: middle; margin-left: 6px; }
    .muted { color: var(--text-tertiary); font-size: 12px; }
    .row-actions { display: flex; align-items: center; justify-content: flex-end; gap: 4px; white-space: nowrap; }
  `]
})
export class JobsComponent implements OnInit, OnDestroy {
  private jobsService = inject(JobsService);
  private instructionsService = inject(InstructionsService);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);
  private router = inject(Router);

  jobs: Job[] = [];
  loading = true;
  columns: HopTableColumn<Job>[] = [
    { key: 'status', label: 'Status', value: j => j.status },
    { key: 'title', label: 'Release', value: j => this.titleOf(j) },
    { key: 'progress', label: 'Progress', value: j => this.progressText(j), sortable: false },
    { key: 'notes', label: 'Notes', value: j => j.counts?.items ?? 0, filterable: false, align: 'end' },
    { key: 'issues', label: 'Issues', value: j => j.counts?.issues ?? 0, filterable: false, align: 'end' },
    { key: 'created', label: 'Created', value: j => new Date(j.created_at), filterable: false },
    { key: 'actions', label: '', sortable: false, filterable: false },
  ];

  private refreshSubscription?: Subscription;

  ngOnInit() {
    this.refreshSubscription = interval(5000)
      .pipe(startWith(0), switchMap(() => this.jobsService.getJobs()))
      .subscribe({
        next: (jobs) => {
          this.jobs = jobs;
          this.loading = false;
        },
        error: (error) => {
          console.error('Failed to load jobs:', error);
          this.loading = false;
        }
      });
  }

  ngOnDestroy() {
    this.refreshSubscription?.unsubscribe();
  }

  titleOf(job: Job): string {
    return job.title || job.output_filename || 'Untitled release';
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

  createJob() {
    this.instructionsService.getInstructionSets().subscribe({
      next: (instructionSets) => {
        if (instructionSets.length === 0) {
          this.snackBar.open('Create an instruction set first', 'Go', { duration: 5000 })
            .onAction().subscribe(() => this.router.navigate(['/instructions']));
          return;
        }
        const dialogRef = this.dialog.open(JobCreateDialogComponent, { width: '640px', data: { instructionSets } });
        dialogRef.afterClosed().subscribe(jobData => {
          if (!jobData) return;
          this.jobsService.createJob(jobData).subscribe({
            next: (job) => {
              this.jobs = [job, ...this.jobs];
              this.router.navigate(['/releases', job.id]);
            },
            error: (error) => {
              this.snackBar.open(error.error?.detail || 'Failed to start the release', 'Close', { duration: 5000 });
            }
          });
        });
      },
      error: (error) => {
        this.snackBar.open(
          error.status === 401 ? 'Session expired. Please log in again.' : 'Failed to load instruction sets',
          'Close', { duration: 5000 }
        );
      }
    });
  }

  rerunJob(job: Job) {
    this.jobsService.rerunJob(job.id).subscribe({
      next: (updated) => {
        this.jobs = this.jobs.map(j => j.id === updated.id ? updated : j);
        this.snackBar.open('Rerun started — unchanged issues keep their notes', 'View', { duration: 5000 })
          .onAction().subscribe(() => this.router.navigate(['/releases', job.id]));
      },
      error: (error) => this.snackBar.open(error.error?.detail || 'Failed to rerun', 'Close', { duration: 5000 })
    });
  }

  cancelJob(job: Job) {
    this.jobsService.cancelJob(job.id).subscribe({
      next: () => {
        job.status = 'cancelled';
        this.snackBar.open('Job cancelled', 'Close', { duration: 3000 });
      },
      error: () => this.snackBar.open('Failed to cancel job', 'Close', { duration: 3000 })
    });
  }

  deleteJob(job: Job) {
    const ref = this.dialog.open(HopConfirmDialogComponent, {
      data: {
        title: 'Delete release',
        message: `Delete "${this.titleOf(job)}" with all its release notes, history and chat? This cannot be undone.`,
        confirmText: 'Delete'
      }
    });
    ref.afterClosed().subscribe(confirmed => {
      if (!confirmed) return;
      this.jobsService.deleteJob(job.id).subscribe({
        next: () => {
          this.jobs = this.jobs.filter(j => j.id !== job.id);
          this.snackBar.open('Release deleted', 'Close', { duration: 3000 });
        },
        error: () => this.snackBar.open('Failed to delete', 'Close', { duration: 3000 })
      });
    });
  }
}
