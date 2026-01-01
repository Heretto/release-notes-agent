import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatExpansionModule } from '@angular/material/expansion';
import { 
  InstructionsService, 
  InstructionSet 
} from '../../core/services/instructions.service';
import { JobsService } from '../../core/services/jobs.service';
import { InstructionDialogComponent } from './instruction-dialog.component';
import { TestQueryDialogComponent } from './test-query-dialog.component';
import { JobCreateDialogComponent } from '../jobs/job-create-dialog.component';

@Component({
  selector: 'app-instructions',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTableModule,
    MatChipsModule,
    MatTooltipModule,
    MatDialogModule,
    MatSnackBarModule,
    MatProgressSpinnerModule,
    MatExpansionModule
  ],
  template: `
    <div class="instructions-container">
      <div class="header">
        <div>
          <h1>Instruction Sets</h1>
          <p class="subtitle">Configure JQL queries and AI prompts for generating release notes</p>
        </div>
        <button mat-raised-button color="primary" (click)="createInstructionSet()">
          <mat-icon>add</mat-icon>
          Create Instruction Set
        </button>
      </div>
      
      <div *ngIf="loading" class="loading-container">
        <mat-spinner></mat-spinner>
      </div>

      <div *ngIf="!loading && instructionSets.length === 0" class="empty-state">
        <mat-card>
          <mat-card-content>
            <mat-icon class="empty-icon">description</mat-icon>
            <h3>No Instruction Sets Yet</h3>
            <p>Create your first instruction set to define how release notes should be generated.</p>
            <button mat-raised-button color="primary" (click)="createInstructionSet()">
              <mat-icon>add</mat-icon>
              Create Your First Instruction Set
            </button>
          </mat-card-content>
        </mat-card>
      </div>

      <div *ngIf="!loading && instructionSets.length > 0" class="instruction-list">
        <mat-card *ngFor="let instruction of instructionSets" class="instruction-card">
          <mat-card-header>
            <div class="card-header-content">
              <div class="title-section">
                <mat-card-title>
                  {{ instruction.name }}
                  <mat-chip *ngIf="instruction.is_default" color="primary" selected>
                    Default
                  </mat-chip>
                </mat-card-title>
                <mat-card-subtitle *ngIf="instruction.description">
                  {{ instruction.description }}
                </mat-card-subtitle>
              </div>
              <div class="actions">
                <button mat-icon-button 
                        [matTooltip]="instruction.is_default ? 'Already default' : 'Set as default'"
                        (click)="setAsDefault(instruction)"
                        [disabled]="instruction.is_default">
                  <mat-icon>star</mat-icon>
                </button>
                <button mat-icon-button 
                        matTooltip="Edit"
                        (click)="editInstructionSet(instruction)">
                  <mat-icon>edit</mat-icon>
                </button>
                <button mat-icon-button 
                        matTooltip="Duplicate"
                        (click)="duplicateInstructionSet(instruction)">
                  <mat-icon>content_copy</mat-icon>
                </button>
                <button mat-icon-button 
                        matTooltip="Delete"
                        color="warn"
                        (click)="deleteInstructionSet(instruction)">
                  <mat-icon>delete</mat-icon>
                </button>
              </div>
            </div>
          </mat-card-header>

          <mat-card-content>
            <mat-expansion-panel>
              <mat-expansion-panel-header>
                <mat-panel-title>
                  <mat-icon>search</mat-icon>
                  JQL Query
                </mat-panel-title>
              </mat-expansion-panel-header>
              <pre class="jql-query">{{ instruction.jql_query }}</pre>
            </mat-expansion-panel>

            <mat-expansion-panel>
              <mat-expansion-panel-header>
                <mat-panel-title>
                  <mat-icon>psychology</mat-icon>
                  System Prompt
                </mat-panel-title>
              </mat-expansion-panel-header>
              <pre class="prompt-text">{{ instruction.system_prompt }}</pre>
            </mat-expansion-panel>

            <mat-expansion-panel *ngIf="instruction.user_instructions">
              <mat-expansion-panel-header>
                <mat-panel-title>
                  <mat-icon>note</mat-icon>
                  Additional Instructions
                </mat-panel-title>
              </mat-expansion-panel-header>
              <pre class="prompt-text">{{ instruction.user_instructions }}</pre>
            </mat-expansion-panel>

            <div class="metadata">
              <span class="meta-item">
                <mat-icon>schedule</mat-icon>
                Created: {{ formatDate(instruction.created_at) }}
              </span>
              <span class="meta-item" *ngIf="instruction.updated_at">
                <mat-icon>update</mat-icon>
                Updated: {{ formatDate(instruction.updated_at) }}
              </span>
            </div>
          </mat-card-content>

          <mat-card-actions>
            <button mat-raised-button color="primary" (click)="testInstructionSet(instruction)">
              <mat-icon>bug_report</mat-icon>
              TEST JQL QUERY
            </button>
            <button mat-raised-button color="accent" (click)="runJob(instruction)">
              <mat-icon>rocket_launch</mat-icon>
              Generate Release Notes
            </button>
          </mat-card-actions>
        </mat-card>
      </div>
    </div>
  `,
  styles: [`
    .instructions-container {
      max-width: 1200px;
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
      justify-content: center;
      padding: 60px;
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

    .instruction-list {
      display: grid;
      gap: 20px;
    }

    .instruction-card {
      margin-bottom: 20px;
    }

    .card-header-content {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      width: 100%;
    }

    .title-section {
      flex: 1;
    }

    .title-section mat-card-title {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
    }

    .actions {
      display: flex;
      gap: 4px;
    }

    mat-expansion-panel {
      margin: 10px 0;
      box-shadow: none !important;
      border: 1px solid #e0e0e0;
    }

    mat-expansion-panel:before {
      display: none;
    }

    mat-panel-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }

    mat-panel-title mat-icon {
      font-size: 20px;
    }

    .jql-query, .prompt-text {
      background: #f5f5f5;
      padding: 15px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-wrap;
      margin: 0;
    }

    .metadata {
      display: flex;
      gap: 20px;
      margin-top: 15px;
      padding-top: 15px;
      border-top: 1px solid #e0e0e0;
      font-size: 12px;
      color: #999;
    }

    .meta-item {
      display: flex;
      align-items: center;
      gap: 5px;
    }

    .meta-item mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    mat-card-actions {
      padding: 16px;
      border-top: 1px solid #e0e0e0;
    }

    mat-chip {
      font-size: 12px;
      min-height: 24px;
      padding: 4px 8px;
    }
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
        this.snackBar.open('Failed to load instruction sets', 'Close', {
          duration: 3000
        });
      }
    });
  }

  createInstructionSet() {
    const dialogRef = this.dialog.open(InstructionDialogComponent, {
      width: '800px',
      maxHeight: '90vh',
      data: null
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.instructionsService.createInstructionSet(result).subscribe({
          next: (instruction) => {
            this.instructionSets.push(instruction);
            this.snackBar.open('Instruction set created successfully', 'Close', {
              duration: 3000
            });
          },
          error: (error) => {
            this.snackBar.open('Failed to create instruction set', 'Close', {
              duration: 3000
            });
            console.error('Error creating instruction set:', error);
          }
        });
      }
    });
  }

  editInstructionSet(instruction: InstructionSet) {
    const dialogRef = this.dialog.open(InstructionDialogComponent, {
      width: '800px',
      maxHeight: '90vh',
      data: instruction
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result && instruction.id) {
        this.instructionsService.updateInstructionSet(instruction.id, result).subscribe({
          next: (updated) => {
            const index = this.instructionSets.findIndex(i => i.id === instruction.id);
            if (index >= 0) {
              this.instructionSets[index] = updated;
            }
            this.snackBar.open('Instruction set updated successfully', 'Close', {
              duration: 3000
            });
          },
          error: (error) => {
            this.snackBar.open('Failed to update instruction set', 'Close', {
              duration: 3000
            });
            console.error('Error updating instruction set:', error);
          }
        });
      }
    });
  }

  duplicateInstructionSet(instruction: InstructionSet) {
    const duplicate = {
      ...instruction,
      name: `${instruction.name} (Copy)`,
      is_default: false
    };
    delete duplicate.id;
    delete duplicate.created_at;
    delete duplicate.updated_at;

    const dialogRef = this.dialog.open(InstructionDialogComponent, {
      width: '800px',
      maxHeight: '90vh',
      data: duplicate
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.instructionsService.createInstructionSet(result).subscribe({
          next: (newInstruction) => {
            this.instructionSets.push(newInstruction);
            this.snackBar.open('Instruction set duplicated successfully', 'Close', {
              duration: 3000
            });
          },
          error: (error) => {
            this.snackBar.open('Failed to duplicate instruction set', 'Close', {
              duration: 3000
            });
            console.error('Error duplicating instruction set:', error);
          }
        });
      }
    });
  }

  deleteInstructionSet(instruction: InstructionSet) {
    if (instruction.id && confirm(`Are you sure you want to delete "${instruction.name}"?`)) {
      this.instructionsService.deleteInstructionSet(instruction.id).subscribe({
        next: () => {
          this.instructionSets = this.instructionSets.filter(i => i.id !== instruction.id);
          this.snackBar.open('Instruction set deleted successfully', 'Close', {
            duration: 3000
          });
        },
        error: (error) => {
          this.snackBar.open('Failed to delete instruction set', 'Close', {
            duration: 3000
          });
          console.error('Error deleting instruction set:', error);
        }
      });
    }
  }

  setAsDefault(instruction: InstructionSet) {
    if (!instruction.id || instruction.is_default) return;

    this.instructionsService.setAsDefault(instruction.id).subscribe({
      next: () => {
        // Update all instruction sets to reflect new default
        this.instructionSets.forEach(i => {
          i.is_default = i.id === instruction.id;
        });
        this.snackBar.open('Default instruction set updated', 'Close', {
          duration: 3000
        });
      },
      error: (error) => {
        this.snackBar.open('Failed to set as default', 'Close', {
          duration: 3000
        });
        console.error('Error setting default:', error);
      }
    });
  }

  testInstructionSet(instruction: InstructionSet) {
    // Debug: Show immediate feedback
    this.snackBar.open('Opening test query dialog...', 'Close', {
      duration: 1000
    });
    
    console.log('Testing instruction set:', instruction);
    
    try {
      const dialogRef = this.dialog.open(TestQueryDialogComponent, {
        width: '900px',
        maxHeight: '90vh',
        data: instruction
      });

      dialogRef.afterClosed().subscribe(() => {
        console.log('Test query dialog closed');
      });
    } catch (error) {
      console.error('Error opening test query dialog:', error);
      this.snackBar.open(`Error: ${error}`, 'Close', {
        duration: 5000
      });
    }
  }

  runJob(instruction: InstructionSet) {
    if (!instruction.id) {
      this.snackBar.open('Invalid instruction set', 'Close', { duration: 3000 });
      return;
    }

    const dialogRef = this.dialog.open(JobCreateDialogComponent, {
      width: '600px',
      data: instruction
    });

    dialogRef.afterClosed().subscribe(jobData => {
      if (jobData) {
        // Create the job
        this.jobsService.createJob(jobData).subscribe({
          next: (job) => {
            this.snackBar.open('Job created successfully! Redirecting to jobs page...', 'Close', {
              duration: 3000
            });
            // Navigate to jobs page to see the new job
            setTimeout(() => {
              this.router.navigate(['/jobs']);
            }, 1500);
          },
          error: (error) => {
            console.error('Failed to create job:', error);
            this.snackBar.open(
              error.error?.detail || 'Failed to create job. Please try again.',
              'Close',
              { duration: 5000 }
            );
          }
        });
      }
    });
  }

  formatDate(dateStr: string | undefined): string {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString();
  }
}