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
import { JqlPart, defaultsOf, jqlParts, missingValues, variableNames } from '../../core/jql-variables';

export interface JobCreateDialogData {
  instructionSets: InstructionSet[];
  selectedId?: string;
}

/** One `{name}` the chosen instruction set's query needs a value for. */
interface StartVariable {
  name: string;
  token: string;
  label: string;
  hint: string;
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
          <p class="agents-line">
            <mat-icon>smart_toy</mat-icon>
            Writer: {{ selectedInstructionSet.writer_agent_name || '—' }}
            · Analysis: {{ selectedInstructionSet.analysis_agent_name || 'same as writer' }}
          </p>
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Release title</mat-label>
          <input matInput [value]="title" (input)="onTitle($any($event.target).value)"
                 placeholder="e.g. Heretto 2026.10">
          <mat-hint>Used as the topic title. Built from the instruction set and the values below until you change it.</mat-hint>
        </mat-form-field>

        <div class="two-up">
          <mat-form-field appearance="outline">
            <mat-label>Output filename</mat-label>
            <input matInput class="mono" [value]="filename" (input)="onFilename($any($event.target).value)"
                   placeholder="release-notes.dita">
            <mat-hint>Topic filename in Heretto and in downloads</mat-hint>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Maximum issues to read</mat-label>
            <input matInput formControlName="max_tickets" type="number" min="1" max="500"
                   placeholder="Default 100">
            <mat-hint>Stops after this many from the query</mat-hint>
          </mat-form-field>
        </div>

        @if (startVariables.length) {
          <div class="vars-card">
            <span class="vars-title">Query variables</span>
            @for (v of startVariables; track v.name) {
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>{{ v.label }}</mat-label>
                <input matInput class="mono" [value]="values[v.name] || ''"
                       (input)="setValue(v.name, $any($event.target).value)" placeholder="Required">
                <mat-hint>{{ v.hint || v.token }}</mat-hint>
              </mat-form-field>
            }
          </div>
        }

        <div class="preview-block">
          <span class="preview-label">Query this release will run</span>
          <div class="query-preview">
            @for (part of previewParts; track $index) {
              @if (part.isVar) { <span class="chip-filled">{{ part.text }}</span> }
              @else if (part.isEmpty) { <span class="chip-missing">{{ part.text }}</span> }
              @else { <span>{{ part.text }}</span> }
            }
          </div>
          @if (missing.length) {
            <p class="preview-missing">Fill in every variable before starting.</p>
          }
        </div>

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
      <button mat-raised-button color="primary" [disabled]="blocked" (click)="onCreate()">
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
    .two-up { display: grid; grid-template-columns: 1.6fr 1fr; gap: 12px; }
    .two-up mat-form-field { width: 100%; }
    .mono { font-family: var(--font-mono); font-size: 13px; }
    .agents-line { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); font-size: 13px; margin: 0 0 12px 0; }
    .agents-line mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .vars-card { border: 1px solid var(--border-default); border-radius: 8px; background: var(--bg-secondary);
      padding: 14px 16px 0; margin-bottom: 8px; }
    .vars-title { display: block; font-size: 13px; font-weight: 600; margin-bottom: 10px; }
    .preview-block { margin-bottom: 8px; }
    .preview-label { display: block; font-size: 12px; font-weight: 500; color: var(--text-secondary); margin-bottom: 4px; }
    .query-preview { background: var(--bg-secondary); border: 1px solid var(--border-default); border-radius: 6px;
      padding: 10px 12px; font-family: var(--font-mono); font-size: 12px; line-height: 1.6; word-break: break-word; }
    .chip-filled { display: inline-block; padding: 0 5px; border-radius: 4px; background: var(--color-primary-bg); color: var(--color-primary-text); font-weight: 600; }
    .chip-missing { display: inline-block; padding: 0 5px; border-radius: 4px; background: var(--color-error-bg); color: var(--color-error-text); font-weight: 600; }
    .preview-missing { font-size: 12px; color: var(--color-error-text); margin: 4px 0 0; }
    .heretto-notice { display: flex; align-items: center; gap: 8px; background: var(--color-primary-bg); color: var(--color-primary-text); padding: 10px 14px; border-radius: 4px; margin-top: 8px; font-size: 14px; }
    mat-dialog-actions { padding: 20px 24px; border-top: 1px solid var(--border-default); }
  `]
})
export class JobCreateDialogComponent implements OnInit {
  form: FormGroup;
  instructionSets: InstructionSet[] = [];
  selectedInstructionSet: InstructionSet | null = null;
  chunkingStrategies = CHUNKING_STRATEGIES;

  /** Values for the chosen set's `{name}` tokens. The server does the substituting. */
  values: Record<string, string> = {};

  /**
   * Title and filename follow the instruction set and the variable values until the person
   * edits one; after that their text is kept, even if they then change a variable.
   */
  private titleTouched = false;
  private filenameTouched = false;
  private typedTitle = '';
  private typedFilename = '';

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
    this.values = defaultsOf(preferred?.variables);

    this.form = this.fb.group({
      instruction_set_id: [preferred?.id, Validators.required],
      max_tickets: [null, [Validators.min(1), Validators.max(500)]]
    });
  }

  ngOnInit() {
    this.form.get('instruction_set_id')?.valueChanges.subscribe(id => {
      const selected = this.instructionSets.find(i => i.id === id);
      if (!selected) return;
      this.selectedInstructionSet = selected;
      // A different set has different variables, so start from its defaults rather than
      // carrying over values that belonged to another query.
      this.values = defaultsOf(selected.variables);
    });
  }

  get startVariables(): StartVariable[] {
    const set = this.selectedInstructionSet;
    if (!set) return [];
    return variableNames(set.jql_query || '').map(name => {
      const spec = set.variables?.[name];
      return { name, token: `{${name}}`, label: spec?.label || name, hint: spec?.hint || '' };
    });
  }

  get missing(): string[] {
    return missingValues(this.selectedInstructionSet?.jql_query || '', this.values);
  }

  get previewParts(): JqlPart[] {
    return jqlParts(this.selectedInstructionSet?.jql_query || '', this.values);
  }

  /** The instruction set's product (or its name) plus every variable value, in query order. */
  get title(): string {
    if (this.titleTouched) return this.typedTitle;
    const set = this.selectedInstructionSet;
    if (!set) return '';
    const parts = [set.product_name || set.name];
    for (const v of this.startVariables) {
      const value = (this.values[v.name] || '').trim();
      if (value) parts.push(value);
    }
    return parts.filter(Boolean).join(' ');
  }

  get filename(): string {
    if (this.filenameTouched) return this.typedFilename;
    const slug = this.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    return `${slug || 'release-notes'}.dita`;
  }

  get blocked(): boolean {
    return !this.form.valid || !this.selectedInstructionSet
      || !!this.missing.length || !this.title.trim() || !this.filename.trim();
  }

  setValue(name: string, value: string): void {
    this.values = { ...this.values, [name]: value };
  }

  onTitle(value: string): void {
    this.titleTouched = true;
    this.typedTitle = value;
  }

  onFilename(value: string): void {
    this.filenameTouched = true;
    this.typedFilename = value;
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onCreate(): void {
    if (this.blocked || !this.selectedInstructionSet) return;
    const jobData: JobCreate = {
      instruction_set_id: this.form.value.instruction_set_id,
      title: this.title.trim() || undefined,
      // No jql_query: the server resolves the instruction set's template from these values,
      // injecting each one as a quoted literal so a value cannot rewrite the query.
      variables: this.values,
      output_filename: this.filename.trim(),
      chunking_strategy: this.selectedInstructionSet.chunking_strategy || 'single',
      max_tickets: this.form.value.max_tickets || undefined,
      publish_to_heretto: this.selectedInstructionSet.publish_to_heretto || false,
      heretto_folder_id: this.selectedInstructionSet.publish_to_heretto
        ? this.selectedInstructionSet.heretto_folder_id : undefined
    };
    this.dialogRef.close(jobData);
  }
}
