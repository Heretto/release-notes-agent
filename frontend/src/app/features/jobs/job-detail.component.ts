import { Component, OnInit, OnDestroy, inject, ChangeDetectionStrategy } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { HopConfirmDialogComponent } from '@heretto/hop-ui';
import { JobsService, Job, JobIssue, JobRequestLog, JobUpdate, ReleaseNoteTopic, JOB_STAGES, JobStage } from '../../core/services/jobs.service';
import { JobEditDialogComponent } from './job-edit-dialog.component';
import { InstructionsService, InstructionSet } from '../../core/services/instructions.service';
import { interval, Subscription } from 'rxjs';
import { switchMap, startWith } from 'rxjs/operators';

type StepState = 'done' | 'current' | 'pending' | 'failed';

@Component({
  selector: 'app-job-detail',
  standalone: true,
  imports: [
    DatePipe,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    MatProgressSpinnerModule,
    MatExpansionModule,
    MatSnackBarModule,
    MatTooltipModule,
    MatDialogModule
  ],
  template: `
    <div class="hop-page">
      @if (loading) {
        <div class="loading-container">
          <mat-spinner></mat-spinner>
          <p>Loading release...</p>
        </div>
      }

      @if (!loading && job) {
        <div class="header">
          <button mat-icon-button (click)="navigateBack()" class="back-button" matTooltip="All releases">
            <mat-icon>arrow_back</mat-icon>
          </button>
          <div class="header-content">
            <h1>
              {{ job.title || job.output_filename || 'Untitled release' }}
              <span [class]="'hop-status-chip hop-status-chip-' + chipClass(job)">{{ statusLabel(job) }}</span>
            </h1>
            <p class="meta">
              @if (instructionSet) { {{ instructionSet.name }} · }
              Run {{ job.run_count || 1 }}
              @if (job.last_run_at) { · last run {{ job.last_run_at | date:'short' }} }
            </p>
          </div>
          <div class="header-actions">
            @if (job.status === 'completed') {
              <a mat-raised-button color="primary" [routerLink]="['/releases', job.id, 'workspace']">
                <mat-icon>edit_note</mat-icon>
                Open workspace
              </a>
            }
            @if (job.status !== 'running' && job.status !== 'pending') {
              <button mat-stroked-button (click)="editJob()" matTooltip="Change this release's configuration">
                <mat-icon>tune</mat-icon>
                Edit
              </button>
            }
            @if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
              <button mat-stroked-button (click)="rerunJob()"
                      matTooltip="Checks Jira for changes and re-reads the instruction set; unchanged issues keep their notes">
                <mat-icon>replay</mat-icon>
                Rerun
              </button>
            }
            @if (job.status === 'running' || job.status === 'pending') {
              <button mat-stroked-button (click)="cancelJob()">
                <mat-icon>cancel</mat-icon>
                Cancel
              </button>
            }
            <button mat-icon-button (click)="deleteJob()" matTooltip="Delete release">
              <mat-icon>delete</mat-icon>
            </button>
          </div>
        </div>

        <!-- Pipeline progress -->
        <mat-card class="pipeline-card" [class.hop-shimmer]="job.status === 'running'">
          <ol class="pipeline">
            @for (step of steps; track step.key) {
              <li [class]="'step step-' + step.state">
                <span class="step-icon">
                  @switch (step.state) {
                    @case ('done') { <mat-icon>check</mat-icon> }
                    @case ('current') { <mat-icon class="spinning">progress_activity</mat-icon> }
                    @case ('failed') { <mat-icon>close</mat-icon> }
                    @default { <mat-icon>circle</mat-icon> }
                  }
                </span>
                <span class="step-label">{{ step.label }}</span>
              </li>
            }
          </ol>
          <p class="pipeline-message" [class.error]="job.status === 'failed'">
            @if (job.status === 'failed') {
              {{ job.error_message || 'The run failed.' }}
            } @else if (job.status === 'pending') {
              Queued — the run starts in a moment.
            } @else {
              {{ job.stage_message || (job.status === 'completed' ? 'Ready for review' : '') }}
            }
          </p>
        </mat-card>

        <div class="columns">
          <mat-card class="summary-card">
            <h2>This release</h2>
            <dl class="facts">
              <div class="fact">
                <dt>Issues</dt>
                <dd>{{ job.counts?.relevant_issues || 0 }} relevant of {{ job.counts?.issues || 0 }}</dd>
              </div>
              <div class="fact">
                <dt>Release notes</dt>
                <dd>
                  {{ job.counts?.items || 0 }}
                  @if (job.counts?.approved_items) { · {{ job.counts!.approved_items }} approved }
                  @if (job.counts?.attention_items) { · <span class="attention">{{ job.counts!.attention_items }} need attention</span> }
                </dd>
              </div>
              <div class="fact">
                <dt>Topics</dt>
                <dd>{{ job.counts?.topics || 0 }} ({{ chunkingLabel(job.chunking_strategy) }})</dd>
              </div>
              <div class="fact">
                <dt>Output file</dt>
                <dd>{{ job.output_filename || '—' }}</dd>
              </div>
              @if (variablesUsed(); as vars) {
                <div class="fact">
                  <dt>Variables</dt>
                  <dd class="vars-fact">{{ vars }}</dd>
                </div>
              }
              <div class="fact">
                <dt>Created</dt>
                <dd>{{ job.created_at | date:'medium' }}</dd>
              </div>
              <div class="fact">
                <dt>Duration</dt>
                <dd>{{ duration() }}</dd>
              </div>
            </dl>

            <!-- The instruction set is a separate thing with its own lifetime: it is shared
                 between releases and is re-read on every run, so what it says here can
                 change without this release changing. Hence its own section rather than
                 more facts in the list above. -->
            <section class="instructions-block">
              <div class="instructions-head">
                <span class="instructions-label">Instructions</span>
                @if (instructionSet) {
                  <a routerLink="/instructions" [queryParams]="{ highlight: instructionSet.id }"
                     class="instructions-name">{{ instructionSet.name }}</a>
                } @else if (job.instruction_set_name) {
                  <span class="instructions-name">{{ job.instruction_set_name }}</span>
                  <span class="muted">no longer available</span>
                } @else {
                  <span class="instructions-name muted">None</span>
                }
              </div>

              <dl class="facts instructions-facts">
                <div class="fact">
                  <dt>Source</dt>
                  <dd>
                    @if (instructionSet?.source_mode === 'releases') {
                      Jira releases in {{ instructionSet!.jira_project }}
                    } @else if (job.uses_instruction_query === false) {
                      Query set on this release
                    } @else {
                      JQL query
                    }
                  </dd>
                </div>
                @if (instructionSet) {
                  <div class="fact">
                    <dt>Agents</dt>
                    <dd>
                      <div class="agent-line">Writer: {{ instructionSet.writer_agent_name || '—' }}</div>
                      <div class="agent-line">Analysis: {{ instructionSet.analysis_agent_name || 'same as writer' }}</div>
                    </dd>
                  </div>
                  <div class="fact">
                    <dt>Guidance</dt>
                    <dd>
                      {{ instructionSet.relevance_guidance ? 'Relevance set' : 'Relevance: default' }}
                      · {{ instructionSet.organization_guidance ? 'Organization set' : 'Organization: default' }}
                    </dd>
                  </div>
                }
              </dl>

              <div class="hop-query-block">
                <span class="hop-query-block-label">{{ instructionSet?.source_mode === 'releases' ? 'JIRA RELEASE QUERY' : 'JQL' }}</span>
                <code>{{ job.jql_query }}</code>
              </div>
            </section>
          </mat-card>

          <mat-card class="topics-card">
            <h2>Topics</h2>
            @if (topics.length === 0) {
              <p class="muted">No topics yet. They appear when the run finishes.</p>
            }
            @for (topic of topics; track topic.id) {
              <div class="topic-row">
                <mat-icon>article</mat-icon>
                <div class="topic-info">
                  <span class="topic-title">{{ topic.title }}</span>
                  <span class="muted">{{ topic.filename }} · {{ topic.item_ids.length }} notes
                    @if (topic.published_at) { · published {{ topic.published_at | date:'short' }} }
                  </span>
                </div>
                <button mat-icon-button matTooltip="Download DITA" (click)="downloadTopic(topic)">
                  <mat-icon>download</mat-icon>
                </button>
              </div>
            }
          </mat-card>
        </div>

        <mat-card class="details-card">
          <mat-tab-group>
            <mat-tab label="Issues ({{ issues.length }})">
              <div class="tab-content">
                @if (issues.length === 0) {
                  <div class="empty-state"><mat-icon>inbox</mat-icon><p>No issues fetched yet</p></div>
                }
                @if (issues.length > 0) {
                  <table class="issues-table">
                    <thead>
                      <tr><th>Key</th><th>Summary</th><th>Type</th><th>Status</th><th>Release notes</th></tr>
                    </thead>
                    <tbody>
                      @for (issue of issues; track issue.id) {
                        <tr [class.dropped]="!issue.in_query">
                          <td>
                            <a [href]="issue.url" target="_blank" rel="noopener" class="issue-key">{{ issue.issue_key }}</a>
                          </td>
                          <td>
                            {{ issue.summary }}
                            @if (!issue.in_query) { <span class="muted"> (no longer matches the query)</span> }
                          </td>
                          <td class="muted">{{ issue.issue_type }}</td>
                          <td class="muted">{{ issue.status }}</td>
                          <td>
                            @if (issue.relevance === 'relevant') {
                              <span class="hop-status-chip hop-status-chip-completed">{{ issue.item_ids.length }} note{{ issue.item_ids.length === 1 ? '' : 's' }}</span>
                            } @else if (issue.relevance === 'not_relevant') {
                              <span class="hop-status-chip" [matTooltip]="issue.relevance_reason || ''">Not user-facing</span>
                            } @else {
                              <span class="hop-status-chip hop-status-chip-pending">Pending</span>
                            }
                          </td>
                        </tr>
                      }
                    </tbody>
                  </table>
                }
              </div>
            </mat-tab>
            <mat-tab label="Run log ({{ requests.length }})">
              <div class="tab-content">
                @if (requests.length === 0) {
                  <div class="empty-state"><mat-icon>http</mat-icon><p>No calls recorded yet</p></div>
                }
                @if (requests.length > 0) {
                  <mat-accordion>
                    @for (request of requests; track request.id) {
                      <mat-expansion-panel>
                        <mat-expansion-panel-header>
                          <mat-panel-title>
                            <span [class]="'hop-status-chip hop-status-chip-' + requestChip(request.status)">{{ request.status }}</span>
                            <span class="request-type">{{ formatRequestType(request.type) }}</span>
                            <span class="request-summary">{{ requestSummary(request) }}</span>
                          </mat-panel-title>
                          <mat-panel-description>
                            {{ request.timestamp | date:'mediumTime' }}
                            @if (request.duration_ms) { <span class="duration">({{ request.duration_ms }} ms)</span> }
                          </mat-panel-description>
                        </mat-expansion-panel-header>
                        <div class="request-details">
                          <h4>Request</h4>
                          <div class="hop-code-panel"><pre>{{ formatJson(request.request_data) }}</pre></div>
                          @if (request.response_data && hasKeys(request.response_data)) {
                            <h4>Response</h4>
                            <div class="hop-code-panel"><pre>{{ formatJson(request.response_data) }}</pre></div>
                          }
                          @if (request.error_message) {
                            <h4>Error</h4>
                            <pre class="error-block">{{ request.error_message }}</pre>
                          }
                        </div>
                      </mat-expansion-panel>
                    }
                  </mat-accordion>
                }
              </div>
            </mat-tab>
          </mat-tab-group>
        </mat-card>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    .loading-container { display: flex; flex-direction: column; align-items: center; padding: 60px; }
    .loading-container p { margin-top: 20px; color: var(--text-secondary); }
    .header { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 20px; }
    .header-content { flex: 1; min-width: 0; }
    .header-content h1 { margin: 0; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .meta { color: var(--text-secondary); font-size: 14px; margin: 4px 0 0 0; }
    .header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
    .pipeline-card { padding: 18px 24px; margin-bottom: 16px; }
    .pipeline { list-style: none; display: flex; gap: 0; margin: 0; padding: 0; flex-wrap: wrap; }
    .step { display: flex; align-items: center; gap: 8px; padding: 6px 18px 6px 0; margin-right: 14px; position: relative; color: var(--text-tertiary); font-size: 13px; }
    .step::after { content: ''; position: absolute; right: 0; top: 50%; width: 10px; height: 1px; background: var(--border-strong); }
    .step:last-child::after { display: none; }
    .step-icon { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--border-strong); background: var(--bg-primary); }
    .step-icon mat-icon { font-size: 16px; width: 16px; height: 16px; }
    .step-done { color: var(--text-primary); }
    .step-done .step-icon { background: var(--color-success); color: white; border-color: var(--color-success); }
    .step-current { color: var(--text-primary); font-weight: 500; }
    .step-current .step-icon { border-color: var(--color-accent); color: var(--text-link); }
    .step-failed .step-icon { background: var(--color-error); color: white; border-color: var(--color-error); }
    .spinning { animation: spin 1.2s linear infinite; }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    .pipeline-message { margin: 12px 0 0 0; color: var(--text-secondary); font-size: 14px; }
    .pipeline-message.error { color: var(--color-error-text); }
    .columns { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 16px; }
    @media (max-width: 1024px) { .columns { grid-template-columns: 1fr; } }
    .summary-card, .topics-card { padding: 18px 24px; }
    .summary-card h2, .topics-card h2 { margin: 0 0 12px 0; font-size: 16px; }
    .facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px 24px; margin: 0 0 16px 0; }
    .instructions-block { border-top: 1px solid var(--border-default); padding-top: 14px; margin-top: 4px; }
    .instructions-head { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; margin-bottom: 12px; }
    /* Label above, name beneath — the same reading order as every dt/dd in the facts. */
    .instructions-label { font-size: 11px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;
      color: var(--text-tertiary); }
    .instructions-name { font-size: 16px; font-weight: 600; color: var(--text-primary); }
    a.instructions-name:hover { color: var(--color-primary); }
    .instructions-facts { margin-bottom: 12px; }
    .agent-line + .agent-line { margin-top: 2px; }
    .fact dt { font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-tertiary); margin-bottom: 2px; }
    .fact dd { margin: 0; font-size: 14px; }
    .vars-fact { font-family: var(--font-mono); font-size: 12px; }
    .instruction-link { color: var(--text-primary); font-weight: 500; }
    .fact .muted { font-size: 12px; color: var(--text-tertiary); }
    .attention { color: var(--color-warning-text); }
    .muted { color: var(--text-tertiary); font-size: 13px; }
    .topic-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border-light); }
    .topic-row:last-child { border-bottom: none; }
    .topic-info { flex: 1; display: flex; flex-direction: column; min-width: 0; }
    .topic-title { font-weight: 500; }
    .details-card { min-height: 400px; }
    .tab-content { padding: 20px; }
    .empty-state { display: flex; flex-direction: column; align-items: center; padding: 48px; color: var(--text-tertiary); }
    .empty-state mat-icon { font-size: 48px; width: 48px; height: 48px; margin-bottom: 10px; }
    .issues-table { width: 100%; border-collapse: collapse; }
    .issues-table th, .issues-table td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border-default); vertical-align: top; }
    .issues-table th { color: var(--text-tertiary); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
    .issues-table tr.dropped td { opacity: 0.6; }
    .issue-key { font-family: var(--font-mono); font-size: 13px; }
    mat-panel-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
    .request-type { font-weight: 500; white-space: nowrap; }
    .request-summary { color: var(--text-secondary); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .duration { color: var(--text-secondary); font-size: 12px; margin-left: 10px; }
    .request-details { padding: 8px 0 16px; }
    .request-details h4 { margin: 12px 0 6px; }
    .request-details pre { max-height: 320px; overflow: auto; font-size: 12px; white-space: pre-wrap; word-break: break-word; }
    .error-block { background: var(--color-error-bg); border: 1px solid var(--color-error-bg); border-radius: 4px; padding: 12px; color: var(--color-error-text); font-family: var(--font-mono); font-size: 12px; white-space: pre-wrap; }
  `]
})
export class JobDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private jobsService = inject(JobsService);
  private instructionsService = inject(InstructionsService);
  private snackBar = inject(MatSnackBar);
  private dialog = inject(MatDialog);

  jobId: string | null = null;
  job: Job | null = null;
  instructionSet: InstructionSet | null = null;
  loading = true;
  issues: JobIssue[] = [];
  requests: JobRequestLog[] = [];
  topics: ReleaseNoteTopic[] = [];
  steps: { key: JobStage; label: string; state: StepState }[] = [];

  private refreshSubscription?: Subscription;
  private lastStatus = '';

  ngOnInit() {
    this.jobId = this.route.snapshot.paramMap.get('id');
    if (!this.jobId) {
      this.router.navigate(['/releases']);
      return;
    }
    this.refreshSubscription = interval(4000)
      .pipe(startWith(0), switchMap(() => this.jobsService.getJob(this.jobId!)))
      .subscribe({
        next: (job) => {
          const changed = job.status !== this.lastStatus || job.status === 'running';
          this.job = job;
          this.steps = this.computeSteps(job);
          if (this.loading) {
            this.loading = false;
            this.loadInstructionSet(job);
          }
          if (changed) {
            this.lastStatus = job.status;
            this.loadDetails();
          }
        },
        error: () => {
          this.snackBar.open('Failed to load the release', 'Close', { duration: 3000 });
          this.router.navigate(['/releases']);
        }
      });
  }

  ngOnDestroy() {
    this.refreshSubscription?.unsubscribe();
  }

  private loadInstructionSet(job: Job) {
    if (!job.instruction_set_id) return;
    this.instructionsService.getInstructionSet(job.instruction_set_id).subscribe({
      next: (set) => this.instructionSet = set,
      error: () => { /* the set may have been deleted; the page still works without it */ }
    });
  }

  private loadDetails() {
    if (!this.jobId) return;
    this.jobsService.getIssues(this.jobId).subscribe({ next: issues => this.issues = issues });
    this.jobsService.getJobRequests(this.jobId).subscribe({ next: requests => this.requests = [...requests].reverse() });
    this.jobsService.getTopics(this.jobId, false).subscribe({ next: topics => this.topics = topics });
  }

  private computeSteps(job: Job): { key: JobStage; label: string; state: StepState }[] {
    const stages = JOB_STAGES;
    const currentIndex = job.stage ? stages.findIndex(s => s.key === job.stage) : -1;
    return stages.map((stage, index) => {
      let state: StepState = 'pending';
      if (job.status === 'completed') state = 'done';
      else if (job.status === 'running') {
        if (index < currentIndex) state = 'done';
        else if (index === currentIndex) state = 'current';
      } else if (job.status === 'failed' || job.status === 'cancelled') {
        if (index < currentIndex) state = 'done';
        else if (index === currentIndex) state = 'failed';
      }
      return { ...stage, state };
    });
  }

  navigateBack() {
    this.router.navigate(['/releases']);
  }

  chipClass(job: Job): string {
    return job.status === 'cancelled' ? 'failed' : job.status;
  }

  statusLabel(job: Job): string {
    if (job.status === 'completed') return 'Ready for review';
    return job.status.charAt(0).toUpperCase() + job.status.slice(1);
  }

  /** `name = value` for the variables this run resolved its query from, '' when it had none. */
  variablesUsed(): string {
    return Object.entries(this.job?.variables || {})
      .map(([name, value]) => `${name} = ${value}`)
      .join(' · ');
  }

  chunkingLabel(strategy: string): string {
    return { single: 'single topic', by_group: 'one per group', by_component: 'one per component' }[strategy] || strategy;
  }

  duration(): string {
    if (!this.job?.started_at) return '—';
    const start = new Date(this.job.started_at).getTime();
    const end = this.job.completed_at ? new Date(this.job.completed_at).getTime() : Date.now();
    const seconds = Math.max(0, Math.floor((end - start) / 1000));
    const minutes = Math.floor(seconds / 60);
    return minutes > 0 ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
  }

  /** Change this release's configuration; the dialog returns only what it changed. */
  editJob() {
    if (!this.job) return;
    const ref = this.dialog.open(JobEditDialogComponent, {
      width: '640px',
      maxHeight: '92vh',
      data: { job: this.job, instructionSet: this.instructionSet }
    });
    ref.afterClosed().subscribe((update: JobUpdate | undefined) => {
      if (!update || !this.job) return;
      this.jobsService.updateJob(this.job.id, update).subscribe({
        next: job => {
          this.job = job;
          this.snackBar.open('Release updated', 'Close', { duration: 3000 });
        },
        error: error => this.snackBar.open(
          typeof error.error?.detail === 'string' ? error.error.detail : 'Could not update the release',
          'Close', { duration: 6000 })
      });
    });
  }

  rerunJob() {
    if (!this.job) return;
    this.jobsService.rerunJob(this.job.id).subscribe({
      next: (job) => {
        this.job = job;
        this.lastStatus = '';
        this.snackBar.open('Rerun started', 'Close', { duration: 3000 });
      },
      error: (error) => this.snackBar.open(error.error?.detail || 'Failed to rerun', 'Close', { duration: 5000 })
    });
  }

  cancelJob() {
    if (!this.job) return;
    this.jobsService.cancelJob(this.job.id).subscribe({
      next: () => this.snackBar.open('Cancelling…', 'Close', { duration: 3000 }),
      error: () => this.snackBar.open('Failed to cancel', 'Close', { duration: 3000 })
    });
  }

  deleteJob() {
    if (!this.job) return;
    const ref = this.dialog.open(HopConfirmDialogComponent, {
      data: { title: 'Delete release', message: 'Delete this release with all its notes, history and chat? This cannot be undone.', confirmText: 'Delete' }
    });
    ref.afterClosed().subscribe(confirmed => {
      if (!confirmed || !this.job) return;
      this.jobsService.deleteJob(this.job.id).subscribe({
        next: () => this.router.navigate(['/releases']),
        error: () => this.snackBar.open('Failed to delete', 'Close', { duration: 3000 })
      });
    });
  }

  downloadTopic(topic: ReleaseNoteTopic) {
    if (!this.job) return;
    this.jobsService.downloadTopic(this.job.id, topic.id).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = topic.filename;
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: () => this.snackBar.open('Failed to download', 'Close', { duration: 3000 })
    });
  }

  requestChip(status: string): string {
    return status === 'success' ? 'completed' : status === 'failed' ? 'failed' : 'pending';
  }

  formatRequestType(type: string): string {
    const map: Record<string, string> = {
      jira_query: 'Jira query', issue_snapshot: 'Issue snapshot', evaluate: 'Evaluate issues',
      consolidate: 'Consolidate notes', organize: 'Organize notes', write: 'Write note',
      heretto_publish: 'Publish to Heretto', agent_run: 'Agent run', ai_generation: 'AI generation',
    };
    return map[type] || type;
  }

  requestSummary(request: JobRequestLog): string {
    const data = request.request_data || {};
    const response = request.response_data || {};
    switch (request.type) {
      case 'write': return data.title ? `“${data.title}”${data.rewrite ? ' (rewrite)' : ''}` : '';
      case 'evaluate': return Array.isArray(data.issues) ? `${data.issues.length} issues → ${response.candidates ?? '?'} candidates` : '';
      case 'consolidate': return `${data.candidates ?? '?'} candidates → ${response.items ?? '?'} notes`;
      case 'organize': return `${data.items ?? '?'} notes into ${(response.groups || []).length || '?'} groups`;
      case 'issue_snapshot': return `${(response.new || []).length} new, ${(response.changed || []).length} changed, ${response.unchanged ?? 0} unchanged`;
      case 'jira_query': return `${response.ticket_count ?? '?'} tickets`;
      case 'heretto_publish': return data.topic || '';
      default: return '';
    }
  }

  hasKeys(obj: any): boolean {
    return obj && typeof obj === 'object' && Object.keys(obj).length > 0;
  }

  formatJson(obj: any): string {
    if (!obj) return '';
    if (typeof obj === 'string') return obj;
    return JSON.stringify(obj, null, 2);
  }
}
