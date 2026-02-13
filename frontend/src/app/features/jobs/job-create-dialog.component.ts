import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';


import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { InstructionSet } from '../../core/services/instructions.service';
import { CredentialsService, AICredential } from '../../core/services/credentials.service';

@Component({
  selector: 'app-job-create-dialog',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,

    MatProgressSpinnerModule,
    MatSelectModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon>rocket_launch</mat-icon>
      Generate Release Notes
    </h2>

    <mat-dialog-content>
      <form [formGroup]="form">
        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Instruction Set</mat-label>
          <mat-select formControlName="instruction_set_id" required>
            <mat-option *ngFor="let ins of instructionSets" [value]="ins.id">
              {{ ins.name }}
              <span *ngIf="ins.is_default"> (Default)</span>
            </mat-option>
          </mat-select>
          <mat-hint>Select which instruction set to use</mat-hint>
        </mat-form-field>

        <div *ngIf="selectedInstructionSet" class="jql-preview">
          <p class="jql-display">{{ selectedInstructionSet.jql_query }}</p>
        </div>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>AI Model (Optional)</mat-label>
          <mat-select formControlName="ai_credential_id">
            <mat-option value="">Use Default</mat-option>
            <mat-option *ngFor="let cred of aiCredentials" [value]="cred.id">
              {{ cred.name }} ({{ cred.provider }})
            </mat-option>
          </mat-select>
          <mat-hint>Select which AI model to use for generation</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Output Filename</mat-label>
          <input matInput formControlName="output_filename"
                 placeholder="release-notes-v2.0.xml" required>
          <mat-hint>Name for the generated DITA file</mat-hint>
          <mat-error *ngIf="form.get('output_filename')?.hasError('required')">
            Output filename is required
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Additional Instructions (Optional)</mat-label>
          <textarea matInput formControlName="additional_instructions"
                    rows="4"
                    placeholder="Any specific requirements or customizations for this release note..."></textarea>
          <mat-hint>Extra context or requirements for the AI</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Custom JQL Query (Optional)</mat-label>
          <textarea matInput formControlName="jql_query"
                    rows="2"
                    placeholder="Leave empty to use instruction set's default query"></textarea>
          <mat-hint>Override the instruction set's JQL query for this job</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Maximum Tickets to Process (Optional)</mat-label>
          <input matInput formControlName="max_tickets"
                 type="number" min="1" max="1000"
                 placeholder="Leave empty for default (100)">
          <mat-hint>Limit the number of tickets to process (default: 100, max: 1000)</mat-hint>
        </mat-form-field>

      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
      <button mat-raised-button color="primary"
              [disabled]="!form.valid || creating"
              (click)="onCreate()">
        <mat-spinner *ngIf="creating" diameter="20" class="inline-spinner"></mat-spinner>
        <span *ngIf="!creating">
          <mat-icon>play_arrow</mat-icon>
          Generate Release Notes
        </span>
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content {
      min-width: 500px;
      max-width: 600px;
    }

    h2 {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .jql-preview {
      margin-bottom: 20px;
    }

    .jql-display {
      background: #f5f5f5;
      padding: 10px;
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      font-family: monospace;
      font-size: 12px;
      margin: 0;
      word-wrap: break-word;
    }

    .full-width {
      width: 100%;
      margin-bottom: 15px;
    }

    .inline-spinner {
      display: inline-block;
      margin-right: 8px;
    }

    mat-dialog-actions {
      padding: 20px 24px;
      border-top: 1px solid #e0e0e0;
    }

    mat-dialog-actions button {
      margin-left: 8px;
    }
  `]
})
export class JobCreateDialogComponent implements OnInit {
  form: FormGroup;
  creating = false;
  aiCredentials: AICredential[] = [];
  instructionSets: InstructionSet[] = [];
  selectedInstructionSet: InstructionSet | null = null;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<JobCreateDialogComponent>,
    private credentialsService: CredentialsService,
    @Inject(MAT_DIALOG_DATA) public data: { instructionSets: InstructionSet[] }
  ) {
    this.instructionSets = data.instructionSets;

    const defaultSet = this.instructionSets.find(i => i.is_default) || this.instructionSets[0];
    this.selectedInstructionSet = defaultSet;

    this.form = this.fb.group({
      instruction_set_id: [defaultSet.id, Validators.required],
      ai_credential_id: [''],
      output_filename: ['', Validators.required],
      additional_instructions: [''],
      jql_query: [''],
      max_tickets: [null, [Validators.min(1), Validators.max(1000)]]
    });
  }

  ngOnInit() {
    // Load AI credentials
    this.credentialsService.getAICredentials().subscribe(
      credentials => this.aiCredentials = credentials
    );

    // Generate default filename based on current date
    const today = new Date();
    const dateStr = today.toISOString().split('T')[0];
    this.form.patchValue({
      output_filename: `release-notes-${dateStr}.xml`
    });

    // Watch for instruction set selection changes
    this.form.get('instruction_set_id')?.valueChanges.subscribe(id => {
      const selected = this.instructionSets.find(i => i.id === id);
      if (selected) {
        this.selectedInstructionSet = selected;
      }
    });
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onCreate(): void {
    if (this.form.valid && !this.creating) {
      this.creating = true;

      const jobData = {
        instruction_set_id: this.form.value.instruction_set_id,
        ai_credential_id: this.form.value.ai_credential_id || undefined,
        jql_query: this.form.value.jql_query || this.selectedInstructionSet?.jql_query,
        output_filename: this.form.value.output_filename,
        additional_instructions: this.form.value.additional_instructions || undefined,
        max_tickets: this.form.value.max_tickets || undefined,
        publish_to_heretto: this.selectedInstructionSet?.publish_to_heretto || false,
        heretto_folder_id: this.selectedInstructionSet?.publish_to_heretto ?
                          this.selectedInstructionSet?.heretto_folder_id : undefined
      };

      this.dialogRef.close(jobData);
    }
  }
}
