import { Component, Inject, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { InstructionSet } from '../../core/services/instructions.service';
import { CHUNKING_STRATEGIES, JobCreate } from '../../core/services/jobs.service';

export interface JobCreateDialogData {
  instructionSets: InstructionSet[];
  selectedId?: string;
}

@Component({
  selector: 'app-job-create-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatSelectModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon>rocket_launch</mat-icon>
      Start a release
    </h2>

    <mat-dialog-content>
      <p class="intro">
        The agents read the issues, decide which ones matter, and draft a release note for each.
        You then finish the notes with the agent in the workspace.
      </p>
      <form [formGroup]="form">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Instruction set</mat-label>
          <mat-select formControlName="instruction_set_id" required>
            @for (ins of instructionSets; track ins.id) {
              <mat-option [value]="ins.id" [disabled]="!ins.writer_agent_id">
                {{ ins.name }}@if (ins.is_default) { (default) }@if (!ins.writer_agent_id) { — no writer agent }
              </mat-option>
            }
          </mat-select>
        </mat-form-field>

        @if (selectedInstructionSet) {
          <div class="hop-query-block">
            <span class="hop-query-block-label">JQL</span>
            <code>{{ form.value.jql_query || selectedInstructionSet.jql_query }}</code>
          </div>
          <p class="agents-line">
            <mat-icon>smart_toy</mat-icon>
            Writer: {{ selectedInstructionSet.writer_agent_name || '—' }}
            · Analysis: {{ selectedInstructionSet.analysis_agent_name || 'same as writer' }}
          </p>
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Release title</mat-label>
          <input matInput formControlName="title" placeholder="e.g. Heretto 2026.10">
          <mat-hint>Used as the topic title. Left empty, the product and version from the query are used.</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Output filename</mat-label>
          <input matInput formControlName="output_filename" placeholder="release-notes-2026-10.dita" required>
          <mat-hint>Base name for the DITA topic files</mat-hint>
          @if (form.get('output_filename')?.hasError('required')) {
            <mat-error>Output filename is required</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Topics</mat-label>
          <mat-select formControlName="chunking_strategy">
            @for (strategy of chunkingStrategies; track strategy.value) {
              <mat-option [value]="strategy.value">{{ strategy.label }} — {{ strategy.hint }}</mat-option>
            }
          </mat-select>
          <mat-hint>Can be changed later in the workspace</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Custom JQL query (optional)</mat-label>
          <textarea matInput formControlName="jql_query" rows="2"
                    placeholder="Leave empty to use the instruction set's query"></textarea>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Maximum issues to read (optional)</mat-label>
          <input matInput formControlName="max_tickets" type="number" min="1" max="500"
                 placeholder="Default 100">
          <mat-hint>Default 100, maximum 500</mat-hint>
        </mat-form-field>

        @if (selectedInstructionSet?.publish_to_heretto) {
          <div class="heretto-notice">
            <mat-icon>cloud_upload</mat-icon>
            <span>Topics will be published to Heretto when the run finishes</span>
          </div>
        }
      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
      <button mat-raised-button color="primary" [disabled]="!form.valid" (click)="onCreate()">
        <mat-icon>play_arrow</mat-icon>
        <span>Start</span>
      </button>
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    mat-dialog-content { min-width: 520px; max-width: 640px; }
    h2 { display: flex; align-items: center; gap: 10px; }
    .intro { color: var(--text-secondary); font-size: 14px; margin: 0 0 16px 0; }
    .full-width { width: 100%; }
    .hop-query-block { margin-bottom: 12px; }
    .agents-line { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); font-size: 13px; margin: 0 0 12px 0; }
    .agents-line mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .heretto-notice { display: flex; align-items: center; gap: 8px; background: var(--color-primary-bg); color: var(--color-primary-text); padding: 10px 14px; border-radius: 4px; margin-top: 8px; font-size: 14px; }
    mat-dialog-actions { padding: 20px 24px; border-top: 1px solid var(--border-default); }
  `]
})
export class JobCreateDialogComponent implements OnInit {
  form: FormGroup;
  instructionSets: InstructionSet[] = [];
  selectedInstructionSet: InstructionSet | null = null;
  chunkingStrategies = CHUNKING_STRATEGIES;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<JobCreateDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: JobCreateDialogData
  ) {
    this.instructionSets = data.instructionSets;
    const preferred = this.instructionSets.find(i => i.id === data.selectedId)
      || this.instructionSets.find(i => i.is_default && i.writer_agent_id)
      || this.instructionSets.find(i => !!i.writer_agent_id)
      || this.instructionSets[0];
    this.selectedInstructionSet = preferred || null;

    this.form = this.fb.group({
      instruction_set_id: [preferred?.id, Validators.required],
      title: [''],
      output_filename: ['', Validators.required],
      chunking_strategy: [preferred?.chunking_strategy || 'single'],
      jql_query: [''],
      max_tickets: [null, [Validators.min(1), Validators.max(500)]]
    });
  }

  ngOnInit() {
    const dateStr = new Date().toISOString().split('T')[0];
    this.form.patchValue({ output_filename: `release-notes-${dateStr}.dita` });

    this.form.get('instruction_set_id')?.valueChanges.subscribe(id => {
      const selected = this.instructionSets.find(i => i.id === id);
      if (selected) {
        this.selectedInstructionSet = selected;
        this.form.patchValue({ chunking_strategy: selected.chunking_strategy || 'single' });
      }
    });
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onCreate(): void {
    if (!this.form.valid || !this.selectedInstructionSet) return;
    const value = this.form.value;
    const jobData: JobCreate = {
      instruction_set_id: value.instruction_set_id,
      title: value.title?.trim() || undefined,
      jql_query: value.jql_query?.trim() || this.selectedInstructionSet.jql_query,
      output_filename: value.output_filename,
      chunking_strategy: value.chunking_strategy,
      max_tickets: value.max_tickets || undefined,
      publish_to_heretto: this.selectedInstructionSet.publish_to_heretto || false,
      heretto_folder_id: this.selectedInstructionSet.publish_to_heretto
        ? this.selectedInstructionSet.heretto_folder_id : undefined
    };
    this.dialogRef.close(jobData);
  }
}
