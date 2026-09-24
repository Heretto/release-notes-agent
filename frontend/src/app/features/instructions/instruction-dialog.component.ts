import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
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

@Component({
  selector: 'app-instruction-dialog',
  standalone: true,
  imports: [
    CommonModule,
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
      {{ data ? 'Edit' : 'Create' }} Instruction Set
    </h2>
    
    <mat-dialog-content>
      <form [formGroup]="form">
        <div class="form-section">
          <h3>Basic Information</h3>
          
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Name</mat-label>
            <input matInput formControlName="name" required>
            <mat-error *ngIf="form.get('name')?.hasError('required')">
              Name is required
            </mat-error>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
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

          <div *ngIf="jiraCredentials.length === 0" class="no-agents-hint">
            <mat-icon>info</mat-icon>
            <span>No Jira credentials yet. Add one in the Credentials page first.</span>
          </div>

          <mat-form-field appearance="outline" class="full-width" *ngIf="jiraCredentials.length > 0">
            <mat-label>Jira Credential</mat-label>
            <mat-select formControlName="jira_credential_id">
              <mat-option [value]="null">Use any available (org default)</mat-option>
              <mat-option *ngFor="let cred of jiraCredentials" [value]="cred.id">
                {{ cred.name }} ({{ cred.server_url }})
              </mat-option>
            </mat-select>
            <mat-hint>Which Jira connection this instruction set's query runs against</mat-hint>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
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
          <h3>Agents</h3>
          <p class="section-hint">
            Add agents to run in series to generate this release note's content. Each
            agent's output becomes the next agent's input.
          </p>

          <div *ngIf="availableAgents.length === 0" class="no-agents-hint">
            <mat-icon>info</mat-icon>
            <span>No agents yet. <a routerLink="/agents">Create one</a> to get started.</span>
          </div>

          <mat-form-field appearance="outline" class="full-width" *ngIf="unselectedAgents.length > 0">
            <mat-label>Add Agent</mat-label>
            <mat-select (selectionChange)="addAgent($event.value)" [value]="null">
              <mat-option *ngFor="let agent of unselectedAgents" [value]="agent.id">
                {{ agent.name }}
              </mat-option>
            </mat-select>
          </mat-form-field>

          <div class="agent-chain" *ngIf="selectedAgents.length > 0">
            <div class="agent-chain-item" *ngFor="let agent of selectedAgents; let i = index">
              <span class="agent-position">{{ i + 1 }}</span>
              <span class="agent-name">{{ agent.name }}</span>
              <span class="agent-arrow" *ngIf="i < selectedAgents.length - 1">&rarr;</span>
              <span class="agent-controls">
                <button mat-icon-button type="button" [disabled]="i === 0"
                        matTooltip="Move up" (click)="moveAgent(i, -1)">
                  <mat-icon>arrow_upward</mat-icon>
                </button>
                <button mat-icon-button type="button" [disabled]="i === selectedAgents.length - 1"
                        matTooltip="Move down" (click)="moveAgent(i, 1)">
                  <mat-icon>arrow_downward</mat-icon>
                </button>
                <button mat-icon-button type="button" color="warn"
                        matTooltip="Remove" (click)="removeAgent(i)">
                  <mat-icon>close</mat-icon>
                </button>
              </span>
            </div>
          </div>

          <p class="agent-chain-empty" *ngIf="availableAgents.length > 0 && selectedAgents.length === 0">
            No agents added yet. At least one agent is required to generate content.
          </p>
        </div>

        <div class="form-section">
          <h3>Heretto CCMS</h3>

          <div class="heretto-toggle">
            <mat-checkbox formControlName="publish_to_heretto">
              Save generated release notes to Heretto
            </mat-checkbox>
          </div>

          <mat-form-field *ngIf="form.get('publish_to_heretto')?.value"
                          appearance="outline" class="full-width">
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
              [disabled]="!form.valid || selectedAgents.length === 0"
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
      color: var(--text-primary);
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
      color: var(--text-tertiary);
      cursor: help;
    }

    .jql-help {
      margin: 15px 0;
      background: var(--bg-secondary);
    }

    .jql-examples {
      padding: 15px;
      font-size: 14px;
    }

    .jql-examples ul {
      margin: 10px 0;
      padding-left: 20px;
    }

    .jql-examples li {
      margin: 8px 0;
    }

    .jql-examples code {
      background: var(--bg-secondary);
      padding: 2px 6px;
      border-radius: 3px;
      font-family: var(--font-mono);
      font-size: 13px;
    }

    .section-hint {
      color: var(--text-secondary);
      font-size: 13px;
      margin: 0 0 15px 0;
    }

    .no-agents-hint {
      display: flex;
      align-items: center;
      gap: 8px;
      background: var(--bg-secondary);
      padding: 10px 14px;
      border-radius: 4px;
      font-size: 14px;
      margin-bottom: 15px;
    }

    .agent-chain {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-bottom: 15px;
    }

    .agent-chain-item {
      display: flex;
      align-items: center;
      gap: 10px;
      background: var(--bg-secondary);
      border: 1px solid var(--border-default);
      border-radius: 4px;
      padding: 8px 12px;
    }

    .agent-position {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: var(--color-primary-bg);
      color: var(--color-primary-text);
      font-size: 12px;
      font-weight: 600;
    }

    .agent-name {
      flex: 1;
      font-size: 14px;
    }

    .agent-arrow {
      color: var(--text-tertiary);
    }

    .agent-controls {
      display: flex;
      gap: 2px;
    }

    .agent-chain-empty {
      color: var(--text-tertiary);
      font-size: 13px;
      font-style: italic;
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
      color: var(--text-secondary);
      font-size: 14px;
    }

    mat-panel-title mat-icon {
      font-size: 20px;
    }
  `]
})
export class InstructionDialogComponent implements OnInit {
  form: FormGroup;

  availableAgents: AgentSummary[] = [];
  selectedAgents: AgentSummary[] = [];
  jiraCredentials: JiraCredential[] = [];

  private initialAgentIds: string[];

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<InstructionDialogComponent>,
    private agentService: HopAgentService,
    private credentialsService: CredentialsService,
    @Inject(MAT_DIALOG_DATA) public data: InstructionSet | null
  ) {
    this.initialAgentIds = data?.agent_ids || [];

    this.form = this.fb.group({
      name: [data?.name || '', Validators.required],
      description: [data?.description || ''],
      jql_query: [data?.jql_query || '', Validators.required],
      jira_credential_id: [data?.jira_credential_id || null],
      heretto_folder_id: [data?.heretto_folder_id || ''],
      publish_to_heretto: [data?.publish_to_heretto || false],
      is_default: [data?.is_default || false]
    });
  }

  ngOnInit(): void {
    this.agentService.listAgents().subscribe(agents => {
      this.availableAgents = agents;
      this.selectedAgents = this.initialAgentIds
        .map(id => agents.find(a => a.id === id))
        .filter((a): a is AgentSummary => !!a);
    });

    this.credentialsService.getJiraCredentials().subscribe(credentials => {
      this.jiraCredentials = credentials;
    });
  }

  get unselectedAgents(): AgentSummary[] {
    const selectedIds = new Set(this.selectedAgents.map(a => a.id));
    return this.availableAgents.filter(a => !selectedIds.has(a.id));
  }

  addAgent(agentId: string): void {
    const agent = this.availableAgents.find(a => a.id === agentId);
    if (agent) {
      this.selectedAgents = [...this.selectedAgents, agent];
    }
  }

  removeAgent(index: number): void {
    this.selectedAgents = this.selectedAgents.filter((_, i) => i !== index);
  }

  moveAgent(index: number, delta: number): void {
    const target = index + delta;
    if (target < 0 || target >= this.selectedAgents.length) return;
    const reordered = [...this.selectedAgents];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    this.selectedAgents = reordered;
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    if (this.form.valid && this.selectedAgents.length > 0) {
      this.dialogRef.close({
        ...this.form.value,
        agent_ids: this.selectedAgents.map(a => a.id)
      });
    }
  }
}