import { Component, Inject, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { RouterLink } from '@angular/router';
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
import { MatSelectModule } from '@angular/material/select';
import { HopAgentService, AgentSummary } from '@heretto/hop-ui';
import { InstructionSet } from '../../core/services/instructions.service';
import { CredentialsService, JiraCredential } from '../../core/services/credentials.service';
import { CHUNKING_STRATEGIES } from '../../core/services/jobs.service';

@Component({
  selector: 'app-instruction-dialog',
  standalone: true,
  imports: [
    RouterLink,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSlideToggleModule,
    MatCheckboxModule,
    MatExpansionModule,
    MatIconModule,
    MatTooltipModule,
    MatSelectModule
  ],
  template: `
    <h2 mat-dialog-title>
      {{ data?.id ? 'Edit' : 'Create' }} Instruction Set
    </h2>

    <mat-dialog-content>
      <form [formGroup]="form">
        <div class="form-section">
          <h3>Basic information</h3>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Name</mat-label>
            <input matInput formControlName="name" required>
            @if (form.get('name')?.hasError('required')) {
              <mat-error>Name is required</mat-error>
            }
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Description</mat-label>
            <textarea matInput formControlName="description" rows="2"></textarea>
            <mat-hint>Brief description of what this instruction set does</mat-hint>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Product name</mat-label>
            <input matInput formControlName="product_name" placeholder="e.g. Heretto CCMS">
            <mat-hint>Used in topic titles and when the agents talk about the product</mat-hint>
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
          <h3>Jira</h3>

          @if (jiraCredentials.length === 0) {
            <div class="hint-box">
              <mat-icon>info</mat-icon>
              <span>No Jira credentials yet. Add one in the Credentials page first.</span>
            </div>
          }

          @if (jiraCredentials.length > 0) {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Jira credential</mat-label>
              <mat-select formControlName="jira_credential_id">
                <mat-option [value]="null">Use any available (org default)</mat-option>
                @for (cred of jiraCredentials; track cred.id) {
                  <mat-option [value]="cred.id">
                    {{ cred.name }} ({{ cred.server_url }})
                  </mat-option>
                }
              </mat-select>
              <mat-hint>Which Jira connection this instruction set's query runs against</mat-hint>
            </mat-form-field>
          }

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>JQL query</mat-label>
            <textarea matInput formControlName="jql_query" rows="3" required
                      placeholder="e.g., project = MYPROJECT AND fixVersion = '1.0' ORDER BY created DESC"></textarea>
            @if (form.get('jql_query')?.hasError('required')) {
              <mat-error>JQL query is required</mat-error>
            }
            <mat-hint>Selects the issues a job evaluates for release notes</mat-hint>
          </mat-form-field>

          <mat-expansion-panel class="jql-help">
            <mat-expansion-panel-header>
              <mat-panel-title>
                <mat-icon>help</mat-icon>
                JQL query examples
              </mat-panel-title>
            </mat-expansion-panel-header>
            <div class="jql-examples">
              <ul>
                <li><code>project = PROJ AND fixVersion = "1.0"</code> — all tickets for version 1.0</li>
                <li><code>project = PROJ AND status = Done AND resolved >= -30d</code> — recently completed tickets</li>
                <li><code>project = PROJ AND labels = "release-notes"</code> — tickets tagged for release notes</li>
                <li><code>project = PROJ AND component = "Backend" ORDER BY priority DESC</code> — one component, by priority</li>
              </ul>
            </div>
          </mat-expansion-panel>
        </div>

        <div class="form-section">
          <h3>Agents</h3>
          <p class="section-hint">
            The writer drafts every release note as DITA and is the agent you work with in the
            workspace. The analysis agent decides which issues matter and how the notes are
            organized; leave it unset to use the writer for both.
          </p>

          @if (agents.length === 0) {
            <div class="hint-box">
              <mat-icon>info</mat-icon>
              <span>No agents yet. <a routerLink="/agents">Create one</a> to get started.</span>
            </div>
          }

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Writer agent</mat-label>
            <mat-select formControlName="writer_agent_id" required>
              @for (agent of agents; track agent.id) {
                <mat-option [value]="agent.id">
                  {{ agent.name }}@if (!agent.ai_configuration) { <span class="muted"> (no AI configuration)</span> }
                </mat-option>
              }
            </mat-select>
            @if (form.get('writer_agent_id')?.hasError('required')) {
              <mat-error>A writer agent is required</mat-error>
            }
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Analysis agent</mat-label>
            <mat-select formControlName="analysis_agent_id">
              <mat-option [value]="null">Same as the writer</mat-option>
              @for (agent of agents; track agent.id) {
                <mat-option [value]="agent.id">{{ agent.name }}</mat-option>
              }
            </mat-select>
            <mat-hint>Evaluates issues and organizes the notes</mat-hint>
          </mat-form-field>
        </div>

        <div class="form-section">
          <h3>Guidance</h3>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>What counts as a change users need to know about</mat-label>
            <textarea matInput formControlName="relevance_guidance" rows="3"
                      placeholder="e.g. Anything that changes the UI, an API response, a default, or a limit. Internal refactors and test work are not relevant."></textarea>
            <mat-hint>Shown to the analysis agent when it decides which issues become release notes</mat-hint>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>How the release notes are organized</mat-label>
            <textarea matInput formControlName="organization_guidance" rows="3"
                      placeholder="e.g. Group as New features, Improvements, Fixes, then Known issues. Put API changes first in each group."></textarea>
            <mat-hint>Shown to the analysis agent when it groups and orders the notes</mat-hint>
          </mat-form-field>
        </div>

        <div class="form-section">
          <h3>Output</h3>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Topics</mat-label>
            <mat-select formControlName="chunking_strategy">
              @for (strategy of chunkingStrategies; track strategy.value) {
                <mat-option [value]="strategy.value">{{ strategy.label }} — {{ strategy.hint }}</mat-option>
              }
            </mat-select>
            <mat-hint>How release notes are split into DITA topics by default; it can be changed per job</mat-hint>
          </mat-form-field>

          <div class="heretto-toggle">
            <mat-checkbox formControlName="publish_to_heretto">
              Publish topics to Heretto when a run finishes
            </mat-checkbox>
          </div>

          @if (form.get('publish_to_heretto')?.value) {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Heretto folder ID</mat-label>
              <input matInput formControlName="heretto_folder_id"
                     placeholder="e.g., 12345-abcde-67890">
              <mat-hint>Target folder in Heretto where the topics are created</mat-hint>
            </mat-form-field>
          }
        </div>
      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
      <button mat-raised-button color="primary"
              [disabled]="!form.valid"
              (click)="onSave()">
        {{ data?.id ? 'Update' : 'Create' }}
      </button>
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    mat-dialog-content { min-width: 600px; max-width: 800px; max-height: 70vh; overflow-y: auto; }
    .form-section { margin-bottom: 28px; }
    .form-section h3 { color: var(--text-primary); margin-bottom: 8px; font-size: 16px; font-weight: 500; }
    .full-width { width: 100%; }
    .default-toggle { display: flex; align-items: center; gap: 10px; margin: 15px 0; }
    .heretto-toggle { margin: 12px 0; }
    .info-icon { font-size: 18px; color: var(--text-tertiary); cursor: help; }
    .jql-help { margin: 15px 0; background: var(--bg-secondary); box-shadow: none !important; }
    .jql-examples { padding: 15px; font-size: 14px; }
    .jql-examples ul { margin: 0; padding-left: 20px; }
    .jql-examples li { margin: 8px 0; }
    .jql-examples code { background: var(--bg-secondary); padding: 2px 6px; border-radius: 3px; font-family: var(--font-mono); font-size: 13px; }
    .section-hint { color: var(--text-secondary); font-size: 13px; margin: 0 0 15px 0; }
    .hint-box { display: flex; align-items: center; gap: 8px; background: var(--bg-secondary); padding: 10px 14px; border-radius: 4px; font-size: 14px; margin-bottom: 15px; }
    .muted { color: var(--text-tertiary); }
    mat-expansion-panel-header { padding-left: 0 !important; }
    mat-panel-title { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 14px; }
    mat-panel-title mat-icon { font-size: 20px; }
  `]
})
export class InstructionDialogComponent implements OnInit {
  form: FormGroup;
  agents: AgentSummary[] = [];
  jiraCredentials: JiraCredential[] = [];
  chunkingStrategies = CHUNKING_STRATEGIES;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<InstructionDialogComponent>,
    private agentService: HopAgentService,
    private credentialsService: CredentialsService,
    @Inject(MAT_DIALOG_DATA) public data: InstructionSet | null
  ) {
    this.form = this.fb.group({
      name: [data?.name || '', Validators.required],
      description: [data?.description || ''],
      product_name: [data?.product_name || ''],
      jql_query: [data?.jql_query || '', Validators.required],
      jira_credential_id: [data?.jira_credential_id || null],
      writer_agent_id: [data?.writer_agent_id || null, Validators.required],
      analysis_agent_id: [data?.analysis_agent_id || null],
      relevance_guidance: [data?.relevance_guidance || ''],
      organization_guidance: [data?.organization_guidance || ''],
      chunking_strategy: [data?.chunking_strategy || 'single'],
      heretto_folder_id: [data?.heretto_folder_id || ''],
      publish_to_heretto: [data?.publish_to_heretto || false],
      is_default: [data?.is_default || false]
    });
  }

  ngOnInit(): void {
    this.agentService.listAgents().subscribe(agents => {
      this.agents = agents.filter(a => a.is_active || a.id === this.data?.writer_agent_id || a.id === this.data?.analysis_agent_id);
      // A single agent is the obvious choice for a new instruction set.
      if (!this.form.value.writer_agent_id && this.agents.length === 1) {
        this.form.patchValue({ writer_agent_id: this.agents[0].id });
      }
    });
    this.credentialsService.getJiraCredentials().subscribe(credentials => {
      this.jiraCredentials = credentials;
    });
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    if (!this.form.valid) return;
    const value = { ...this.form.value };
    for (const key of ['description', 'product_name', 'relevance_guidance', 'organization_guidance', 'heretto_folder_id']) {
      if (typeof value[key] === 'string' && !value[key].trim()) value[key] = null;
    }
    this.dialogRef.close(value);
  }
}
