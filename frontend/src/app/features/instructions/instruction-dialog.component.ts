import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { InstructionSet } from '../../core/services/instructions.service';

@Component({
  selector: 'app-instruction-dialog',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSlideToggleModule,
    MatCheckboxModule,
    MatExpansionModule,
    MatIconModule,
    MatTooltipModule
  ],
  template: `
    <h2 mat-dialog-title>
      {{ data ? 'Edit' : 'Create' }} Instruction Set
    </h2>
    
    <mat-dialog-content>
      <form [formGroup]="form">
        <div class="form-section">
          <h3>Basic Information</h3>
          
          <mat-form-field appearance="fill" class="full-width">
            <mat-label>Name</mat-label>
            <input matInput formControlName="name" required>
            <mat-error *ngIf="form.get('name')?.hasError('required')">
              Name is required
            </mat-error>
          </mat-form-field>

          <mat-form-field appearance="fill" class="full-width">
            <mat-label>Description</mat-label>
            <textarea matInput formControlName="description" rows="2"></textarea>
            <mat-hint>Brief description of what this instruction set does</mat-hint>
          </mat-form-field>

          <div class="default-toggle">
            <mat-slide-toggle formControlName="is_default">
              Set as default instruction set
            </mat-slide-toggle>
            <mat-icon 
              matTooltip="Default instruction sets are pre-selected when creating new jobs"
              class="info-icon">
              info
            </mat-icon>
          </div>
        </div>

        <div class="form-section">
          <h3>Jira Configuration</h3>
          
          <mat-form-field appearance="fill" class="full-width">
            <mat-label>JQL Query</mat-label>
            <textarea matInput formControlName="jql_query" rows="3" required
                      placeholder="e.g., project = MYPROJECT AND fixVersion = '1.0' ORDER BY created DESC"></textarea>
            <mat-error *ngIf="form.get('jql_query')?.hasError('required')">
              JQL query is required
            </mat-error>
            <mat-hint>Enter the Jira Query Language (JQL) to select tickets for processing</mat-hint>
          </mat-form-field>

          <mat-expansion-panel class="jql-help">
            <mat-expansion-panel-header>
              <mat-panel-title>
                <mat-icon>help</mat-icon>
                JQL Query Examples
              </mat-panel-title>
            </mat-expansion-panel-header>
            
            <div class="jql-examples">
              <p><strong>Common JQL Patterns:</strong></p>
              <ul>
                <li><code>project = PROJ AND fixVersion = "1.0"</code> - All tickets for version 1.0</li>
                <li><code>project = PROJ AND updated >= -7d</code> - Tickets updated in last 7 days</li>
                <li><code>project = PROJ AND status = Done AND resolved >= -30d</code> - Recently completed tickets</li>
                <li><code>project = PROJ AND type = Bug AND priority in (High, Critical)</code> - High priority bugs</li>
                <li><code>project = PROJ AND labels = "release-notes"</code> - Tickets tagged for release notes</li>
                <li><code>project = PROJ AND component = "Backend" ORDER BY priority DESC</code> - Backend tickets by priority</li>
              </ul>
            </div>
          </mat-expansion-panel>
        </div>

        <div class="form-section">
          <h3>LLM Instructions</h3>
          
          <mat-form-field appearance="fill" class="full-width">
            <mat-label>System Prompt</mat-label>
            <textarea matInput formControlName="system_prompt" rows="6" required
                      placeholder="You are a technical writer creating release notes from Jira tickets..."></textarea>
            <mat-error *ngIf="form.get('system_prompt')?.hasError('required')">
              System prompt is required
            </mat-error>
            <mat-hint>Instructions for the AI on how to process and format the release notes</mat-hint>
          </mat-form-field>

          <mat-form-field appearance="fill" class="full-width">
            <mat-label>Additional User Instructions (Optional)</mat-label>
            <textarea matInput formControlName="user_instructions" rows="4"
                      placeholder="Focus on user-facing changes, group by feature area..."></textarea>
            <mat-hint>Additional context or specific requirements for this instruction set</mat-hint>
          </mat-form-field>

          <mat-expansion-panel class="prompt-tips">
            <mat-expansion-panel-header>
              <mat-panel-title>
                <mat-icon>tips_and_updates</mat-icon>
                Prompt Writing Tips
              </mat-panel-title>
            </mat-expansion-panel-header>

            <div class="tips-content">
              <p><strong>Effective System Prompts Should Include:</strong></p>
              <ul>
                <li>The role/persona (e.g., "You are a technical writer...")</li>
                <li>The task (e.g., "Create release notes from Jira tickets...")</li>
                <li>Output format (e.g., "Format as DITA XML topics...")</li>
                <li>Tone and style (e.g., "Use professional, concise language...")</li>
                <li>Specific requirements (e.g., "Group by feature area, prioritize user impact...")</li>
              </ul>

              <p><strong>Example System Prompt:</strong></p>
              <pre class="example-prompt">{{ examplePrompt }}</pre>
            </div>
          </mat-expansion-panel>
        </div>

        <div class="form-section">
          <h3>Heretto CCMS</h3>

          <div class="heretto-toggle">
            <mat-checkbox formControlName="publish_to_heretto">
              Save generated release notes to Heretto
            </mat-checkbox>
          </div>

          <mat-form-field *ngIf="form.get('publish_to_heretto')?.value"
                          appearance="fill" class="full-width">
            <mat-label>Heretto Folder ID</mat-label>
            <input matInput formControlName="heretto_folder_id"
                   placeholder="e.g., 12345-abcde-67890">
            <mat-hint>Target folder in Heretto where generated content will be saved</mat-hint>
          </mat-form-field>
        </div>
      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
      <button mat-raised-button color="primary" 
              [disabled]="!form.valid"
              (click)="onSave()">
        {{ data ? 'Update' : 'Create' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content {
      min-width: 600px;
      max-width: 800px;
      max-height: 70vh;
      overflow-y: auto;
    }

    .form-section {
      margin-bottom: 30px;
    }

    .form-section h3 {
      color: #333;
      margin-bottom: 15px;
      font-size: 16px;
      font-weight: 500;
    }

    .full-width {
      width: 100%;
      margin-bottom: 15px;
    }

    .default-toggle {
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 15px 0;
    }

    .heretto-toggle {
      margin-bottom: 15px;
    }

    .info-icon {
      font-size: 18px;
      color: #999;
      cursor: help;
    }

    .jql-help, .prompt-tips {
      margin: 15px 0;
      background: #f9f9f9;
    }

    .jql-examples, .tips-content {
      padding: 15px;
      font-size: 14px;
    }

    .jql-examples ul, .tips-content ul {
      margin: 10px 0;
      padding-left: 20px;
    }

    .jql-examples li, .tips-content li {
      margin: 8px 0;
    }

    .jql-examples code {
      background: #e8e8e8;
      padding: 2px 6px;
      border-radius: 3px;
      font-family: monospace;
      font-size: 13px;
    }

    .example-prompt {
      background: #f5f5f5;
      padding: 12px;
      border-radius: 4px;
      font-size: 12px;
      line-height: 1.5;
      white-space: pre-wrap;
      margin-top: 10px;
    }

    mat-expansion-panel {
      box-shadow: none !important;
    }

    mat-expansion-panel-header {
      padding-left: 0 !important;
    }

    mat-panel-title {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #666;
      font-size: 14px;
    }

    mat-panel-title mat-icon {
      font-size: 20px;
    }
  `]
})
export class InstructionDialogComponent {
  form: FormGroup;
  
  examplePrompt = `You are a technical writer creating professional release notes for a software product.

Your task is to analyze the provided Jira tickets and create clear, concise release notes that:
1. Summarize the changes in user-friendly language
2. Group related changes by feature area or component
3. Highlight breaking changes, new features, improvements, and bug fixes
4. Use consistent terminology and formatting
5. Focus on the impact to end users rather than technical implementation details

Format the output as structured DITA XML topics following the standard release notes template.
Prioritize the most impactful changes first and ensure all content is accurate and complete.`;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<InstructionDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: InstructionSet | null
  ) {
    this.form = this.fb.group({
      name: [data?.name || '', Validators.required],
      description: [data?.description || ''],
      jql_query: [data?.jql_query || '', Validators.required],
      system_prompt: [data?.system_prompt || this.getDefaultSystemPrompt(), Validators.required],
      user_instructions: [data?.user_instructions || ''],
      heretto_folder_id: [data?.heretto_folder_id || ''],
      publish_to_heretto: [data?.publish_to_heretto || false],
      is_default: [data?.is_default || false]
    });
  }

  getDefaultSystemPrompt(): string {
    return `You are a technical writer creating professional release notes from Jira tickets.

Analyze the provided tickets and create clear, user-focused release notes that:
- Summarize changes in user-friendly language
- Group by feature area
- Highlight new features, improvements, and fixes
- Use consistent formatting

Format as DITA XML topics suitable for technical documentation.`;
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    if (this.form.valid) {
      this.dialogRef.close(this.form.value);
    }
  }
}