import { Component, OnInit, inject, ChangeDetectionStrategy } from '@angular/core';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatMenuModule } from '@angular/material/menu';
import { HopConfirmDialogComponent } from '@heretto/hop-ui';
import { InstructionsService, InstructionSet } from '../../core/services/instructions.service';
import { JobsService, CHUNKING_STRATEGIES } from '../../core/services/jobs.service';
import { InstructionDialogComponent } from './instruction-dialog.component';
import { TestQueryDialogComponent } from './test-query-dialog.component';
import { JobCreateDialogComponent } from '../jobs/job-create-dialog.component';

@Component({
  selector: 'app-instructions',
  standalone: true,
  imports: [
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
    MatDialogModule,
    MatSnackBarModule,
    MatProgressSpinnerModule,
    MatMenuModule
  ],
  template: `
    <div class="hop-page">
      <div class="header">
        <div>
          <h1>Instruction Sets</h1>
          <p class="subtitle">Which issues to read, which agents write, and how the release notes are organized</p>
        </div>
        <button mat-raised-button color="primary" (click)="createInstructionSet()">
          <mat-icon>add</mat-icon>
          Create Instruction Set
        </button>
      </div>

      @if (loading) {
        <div class="loading-container"><mat-spinner></mat-spinner></div>
      }

      @if (!loading && instructionSets.length === 0) {
        <div class="empty-state">
          <mat-card>
            <mat-card-content>
              <mat-icon class="empty-icon">description</mat-icon>
              <h3>No instruction sets yet</h3>
              <p>An instruction set tells a job which Jira issues to read and which agents turn them into release notes.</p>
              <button mat-raised-button color="primary" (click)="createInstructionSet()">
                <mat-icon>add</mat-icon>
                Create your first instruction set
              </button>
            </mat-card-content>
          </mat-card>
        </div>
      }

      @if (!loading && instructionSets.length > 0) {
        <div class="instruction-list">
          @for (instruction of instructionSets; track instruction.id) {
            <mat-card class="instruction-card" [class.hop-card-accent]="instruction.is_default">
              <div class="card-header-row">
                <div class="title-section">
                  <h2 class="card-title">
                    {{ instruction.name }}
                    @if (instruction.is_default) {
                      <span class="hop-status-chip hop-status-chip-running">Default</span>
                    }
                  </h2>
                  @if (instruction.description) {
                    <p class="card-subtitle">{{ instruction.description }}</p>
                  }
                </div>
                <div class="actions">
                  <button mat-icon-button
                    [matTooltip]="instruction.is_default ? 'Already default' : 'Set as default'"
                    (click)="setAsDefault(instruction)"
                    [disabled]="instruction.is_default">
                    <mat-icon>star</mat-icon>
                  </button>
                  <button mat-icon-button matTooltip="Edit" (click)="editInstructionSet(instruction)">
                    <mat-icon>edit</mat-icon>
                  </button>
                  <button mat-icon-button [matMenuTriggerFor]="menu" matTooltip="More">
                    <mat-icon>more_vert</mat-icon>
                  </button>
                  <mat-menu #menu="matMenu">
                    <button mat-menu-item (click)="duplicateInstructionSet(instruction)">
                      <mat-icon>content_copy</mat-icon><span>Duplicate</span>
                    </button>
                    <button mat-menu-item (click)="testInstructionSet(instruction)">
                      <mat-icon>bug_report</mat-icon><span>Test JQL query</span>
                    </button>
                    <button mat-menu-item (click)="deleteInstructionSet(instruction)">
                      <mat-icon>delete</mat-icon><span>Delete</span>
                    </button>
                  </mat-menu>
                </div>
              </div>

              <div class="hop-query-block">
                <span class="hop-query-block-label">JQL</span>
                <code>{{ instruction.jql_query }}</code>
              </div>

              <dl class="facts">
                <div class="fact">
                  <dt>Product</dt>
                  <dd>{{ instruction.product_name || '—' }}</dd>
                </div>
                <div class="fact">
                  <dt>Writer agent</dt>
                  <dd>
                    @if (instruction.writer_agent_name) {
                      {{ instruction.writer_agent_name }}
                    } @else {
                      <span class="warning-text"><mat-icon>warning</mat-icon> None — jobs cannot run</span>
                    }
                  </dd>
                </div>
                <div class="fact">
                  <dt>Analysis agent</dt>
                  <dd>{{ instruction.analysis_agent_name || 'Same as writer' }}</dd>
                </div>
                <div class="fact">
                  <dt>Topics</dt>
                  <dd>{{ chunkingLabel(instruction.chunking_strategy) }}</dd>
                </div>
                <div class="fact">
                  <dt>Heretto</dt>
                  <dd>
                    @if (instruction.publish_to_heretto) {
                      Publish to folder <code>{{ instruction.heretto_folder_id || '?' }}</code>
                    } @else {
                      Manual publish from the workspace
                    }
                  </dd>
                </div>
              </dl>

              @if (instruction.relevance_guidance || instruction.organization_guidance) {
                <div class="guidance">
                  @if (instruction.relevance_guidance) {
                    <p><strong>Relevance:</strong> {{ instruction.relevance_guidance }}</p>
                  }
                  @if (instruction.organization_guidance) {
                    <p><strong>Organization:</strong> {{ instruction.organization_guidance }}</p>
                  }
                </div>
              }

              <div class="card-footer">
                <span class="meta">
                  Created {{ formatDate(instruction.created_at) }}
                  @if (instruction.updated_at) { · Updated {{ formatDate(instruction.updated_at) }} }
                </span>
                <span class="footer-actions">
                  <button mat-stroked-button (click)="testInstructionSet(instruction)">
                    <mat-icon>bug_report</mat-icon>
                    Test query
                  </button>
                  <button mat-raised-button color="primary" (click)="runJob(instruction)"
                          [disabled]="!instruction.writer_agent_id"
                          [matTooltip]="instruction.writer_agent_id ? '' : 'Pick a writer agent first'">
                    <mat-icon>rocket_launch</mat-icon>
                    Start a release
                  </button>
                </span>
              </div>
            </mat-card>
          }
        </div>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; gap: 16px; flex-wrap: wrap; }
    .header h1 { margin: 0; }
    .subtitle { color: var(--text-secondary); margin: 5px 0 0 0; }
    .loading-container { display: flex; justify-content: center; padding: 60px; }
    .empty-state { text-align: center; padding: 40px 20px; }
    .empty-state mat-card { max-width: 520px; margin: 0 auto; padding: 40px; }
    .empty-icon { font-size: 64px; width: 64px; height: 64px; color: var(--border-default); margin: 0 auto 20px; }
    .empty-state h3 { color: var(--text-primary); margin-bottom: 10px; }
    .empty-state p { color: var(--text-secondary); margin-bottom: 20px; }
    .instruction-list { display: grid; gap: 16px; }
    .instruction-card { padding: 20px 24px; }
    .card-header-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
    .card-title { display: flex; align-items: center; gap: 10px; margin: 0 0 4px 0; font-size: 18px; }
    .card-subtitle { margin: 0; color: var(--text-secondary); }
    .actions { display: flex; gap: 2px; flex-shrink: 0; }
    .hop-query-block { margin: 16px 0; }
    .facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px 24px; margin: 0; }
    .fact dt { font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-tertiary); margin-bottom: 2px; }
    .fact dd { margin: 0; font-size: 14px; }
    .fact code { font-family: var(--font-mono); font-size: 12px; background: var(--bg-secondary); padding: 1px 5px; border-radius: 3px; }
    .warning-text { color: var(--color-warning-text); display: inline-flex; align-items: center; gap: 4px; }
    .warning-text mat-icon { font-size: 16px; width: 16px; height: 16px; }
    .guidance { margin-top: 14px; padding: 10px 14px; background: var(--bg-secondary); border-radius: 8px; font-size: 13px; color: var(--text-secondary); }
    .guidance p { margin: 4px 0; }
    .card-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--border-default); gap: 12px; flex-wrap: wrap; }
    .meta { font-size: 12px; color: var(--text-tertiary); }
    .footer-actions { display: flex; gap: 8px; }
  `]
})
export class InstructionsComponent implements OnInit {
  private instructionsService = inject(InstructionsService);
  private jobsService = inject(JobsService);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);
  private router = inject(Router);

  instructionSets: InstructionSet[] = [];
  loading = false;

  ngOnInit() {
    this.loadInstructionSets();
  }

  loadInstructionSets() {
    this.loading = true;
    this.instructionsService.getInstructionSets().subscribe({
      next: (instructions) => {
        this.instructionSets = instructions;
        this.loading = false;
      },
      error: (error) => {
        console.error('Failed to load instruction sets:', error);
        this.loading = false;
        this.snackBar.open('Failed to load instruction sets', 'Close', { duration: 3000 });
      }
    });
  }

  chunkingLabel(strategy: string | undefined): string {
    return CHUNKING_STRATEGIES.find(s => s.value === strategy)?.label || 'Single topic';
  }

  createInstructionSet() {
    const dialogRef = this.dialog.open(InstructionDialogComponent, { width: '800px', maxHeight: '90vh', data: null });
    dialogRef.afterClosed().subscribe(result => {
      if (!result) return;
      this.instructionsService.createInstructionSet(result).subscribe({
        next: (instruction) => {
          this.instructionSets.push(instruction);
          this.snackBar.open('Instruction set created', 'Close', { duration: 3000 });
        },
        error: (error) => {
          this.snackBar.open(error.error?.detail || 'Failed to create instruction set', 'Close', { duration: 5000 });
        }
      });
    });
  }

  editInstructionSet(instruction: InstructionSet) {
    const dialogRef = this.dialog.open(InstructionDialogComponent, { width: '800px', maxHeight: '90vh', data: instruction });
    dialogRef.afterClosed().subscribe(result => {
      if (!result || !instruction.id) return;
      this.instructionsService.updateInstructionSet(instruction.id, result).subscribe({
        next: (updated) => {
          const index = this.instructionSets.findIndex(i => i.id === instruction.id);
          if (index >= 0) this.instructionSets[index] = updated;
          if (updated.is_default) {
            this.instructionSets.forEach(i => { if (i.id !== updated.id) i.is_default = false; });
          }
          this.snackBar.open('Instruction set updated', 'Close', { duration: 3000 });
        },
        error: (error) => {
          this.snackBar.open(error.error?.detail || 'Failed to update instruction set', 'Close', { duration: 5000 });
        }
      });
    });
  }

  duplicateInstructionSet(instruction: InstructionSet) {
    const duplicate: InstructionSet = { ...instruction, name: `${instruction.name} (Copy)`, is_default: false };
    delete duplicate.id;
    delete duplicate.created_at;
    delete duplicate.updated_at;
    const dialogRef = this.dialog.open(InstructionDialogComponent, { width: '800px', maxHeight: '90vh', data: duplicate });
    dialogRef.afterClosed().subscribe(result => {
      if (!result) return;
      this.instructionsService.createInstructionSet(result).subscribe({
        next: (created) => {
          this.instructionSets.push(created);
          this.snackBar.open('Instruction set duplicated', 'Close', { duration: 3000 });
        },
        error: (error) => {
          this.snackBar.open(error.error?.detail || 'Failed to duplicate instruction set', 'Close', { duration: 5000 });
        }
      });
    });
  }

  deleteInstructionSet(instruction: InstructionSet) {
    if (!instruction.id) return;
    const ref = this.dialog.open(HopConfirmDialogComponent, {
      data: { title: 'Delete instruction set', message: `Delete "${instruction.name}"? Releases already run from it are kept.`, confirmText: 'Delete' }
    });
    ref.afterClosed().subscribe(confirmed => {
      if (!confirmed) return;
      this.instructionsService.deleteInstructionSet(instruction.id!).subscribe({
        next: () => {
          this.instructionSets = this.instructionSets.filter(i => i.id !== instruction.id);
          this.snackBar.open('Instruction set deleted', 'Close', { duration: 3000 });
        },
        error: () => this.snackBar.open('Failed to delete instruction set', 'Close', { duration: 3000 })
      });
    });
  }

  setAsDefault(instruction: InstructionSet) {
    if (!instruction.id || instruction.is_default) return;
    this.instructionsService.setAsDefault(instruction.id).subscribe({
      next: () => {
        this.instructionSets.forEach(i => { i.is_default = i.id === instruction.id; });
        this.snackBar.open('Default instruction set updated', 'Close', { duration: 3000 });
      },
      error: () => this.snackBar.open('Failed to set as default', 'Close', { duration: 3000 })
    });
  }

  testInstructionSet(instruction: InstructionSet) {
    this.dialog.open(TestQueryDialogComponent, { width: '900px', maxHeight: '90vh', data: instruction });
  }

  runJob(instruction: InstructionSet) {
    if (!instruction.id) return;
    const dialogRef = this.dialog.open(JobCreateDialogComponent, {
      width: '640px',
      data: { instructionSets: this.instructionSets, selectedId: instruction.id }
    });
    dialogRef.afterClosed().subscribe(jobData => {
      if (!jobData) return;
      this.jobsService.createJob(jobData).subscribe({
        next: (job) => {
          this.snackBar.open('Release started', 'Close', { duration: 3000 });
          this.router.navigate(['/releases', job.id]);
        },
        error: (error) => {
          this.snackBar.open(error.error?.detail || 'Failed to start the release', 'Close', { duration: 5000 });
        }
      });
    });
  }

  formatDate(dateStr: string | undefined): string {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString();
  }
}
