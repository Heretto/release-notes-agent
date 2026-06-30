import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { CredentialsService } from '../../core/services/credentials.service';

export interface AICredential {
  id?: string;
  type: 'AI';
  name: string;
  provider: string;
  api_key: string;
  model?: string;
  base_url?: string;
  organization_id?: string;
  azure_endpoint?: string;
  deployment_name?: string;
  api_version?: string;
  created_at?: string;
  updated_at?: string;
}

@Component({
  selector: 'app-ai-credential-dialog',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatSelectModule,
    MatTabsModule,
    MatExpansionModule,
    MatProgressSpinnerModule
  ],
  template: `
    <h2 mat-dialog-title>{{ data ? 'Edit' : 'Add' }} AI Credential</h2>
    <mat-dialog-content>
      <div *ngIf="data" class="current-values">
        <div class="info-box">
          <mat-icon>info</mat-icon>
          <span>Current credential details:</span>
        </div>
        <div class="credential-display">
          <div class="field-display">
            <strong>Provider:</strong> {{ data.provider }}
          </div>
          <div class="field-display">
            <strong>Model:</strong> {{ data.model || 'Default' }}
          </div>
          <div class="field-display">
            <strong>API Key:</strong> {{ maskApiKey(data.api_key) }}
          </div>
          <div *ngIf="data.provider === 'azure'" class="field-display">
            <strong>Endpoint:</strong> {{ data.azure_endpoint }}
          </div>
          <div *ngIf="data.provider === 'azure'" class="field-display">
            <strong>Deployment:</strong> {{ data.deployment_name }}
          </div>
        </div>
      </div>

      <form [formGroup]="form">
        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Name</mat-label>
          <input matInput formControlName="name" required 
                 placeholder="My OpenAI Credential">
          <mat-hint>A friendly name to identify this credential</mat-hint>
          <mat-error *ngIf="form.get('name')?.hasError('required')">
            Name is required
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>AI Provider</mat-label>
          <mat-select formControlName="provider" required>
            <mat-option value="openai">
              <mat-icon>smart_toy</mat-icon>
              OpenAI (GPT-4, GPT-3.5)
            </mat-option>
            <mat-option value="anthropic">
              <mat-icon>psychology</mat-icon>
              Anthropic (Claude)
            </mat-option>
            <mat-option value="gemini">
              <mat-icon>auto_awesome</mat-icon>
              Google AI Studio (Gemini)
            </mat-option>
            <mat-option value="azure">
              <mat-icon>cloud</mat-icon>
              Azure OpenAI
            </mat-option>
            <mat-option value="custom">
              <mat-icon>settings</mat-icon>
              Custom/Other
            </mat-option>
          </mat-select>
          <mat-error *ngIf="form.get('provider')?.hasError('required')">
            Provider is required
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>API Key</mat-label>
          <input matInput type="password" formControlName="api_key" 
                 [placeholder]="data ? 'Enter new key (leave empty to keep current)' : 'Enter API key'"
                 [required]="!data">
          <mat-hint *ngIf="data">Leave empty to keep current API key</mat-hint>
          <mat-error *ngIf="form.get('api_key')?.hasError('required')">
            API Key is required
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width">
          <mat-label>Model (Optional)</mat-label>
          <input matInput formControlName="model" 
                 [placeholder]="getModelPlaceholder()">
          <mat-hint>{{ getModelHint() }}</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width"
                        *ngIf="showAzureFields">
          <mat-label>Azure Endpoint</mat-label>
          <input matInput formControlName="azure_endpoint"
                 placeholder="https://my-resource.openai.azure.com">
          <mat-hint>Your Azure OpenAI resource endpoint URL</mat-hint>
          <mat-error *ngIf="form.get('azure_endpoint')?.hasError('required')">
            Azure endpoint is required
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width"
                        *ngIf="showAzureFields">
          <mat-label>Deployment Name</mat-label>
          <input matInput formControlName="deployment_name"
                 placeholder="e.g., gpt-4o-deployment">
          <mat-hint>The deployment name you gave the model in Azure AI Foundry</mat-hint>
          <mat-error *ngIf="form.get('deployment_name')?.hasError('required')">
            Deployment name is required
          </mat-error>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width"
                        *ngIf="showAzureFields">
          <mat-label>API Version (Optional)</mat-label>
          <input matInput formControlName="api_version"
                 placeholder="2024-05-01-preview">
          <mat-hint>Azure OpenAI API version (defaults to 2024-05-01-preview)</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width"
                        *ngIf="showBaseUrl">
          <mat-label>Base URL (Optional)</mat-label>
          <input matInput formControlName="base_url"
                 placeholder="https://api.openai.com/v1">
          <mat-hint>Custom API endpoint (for self-hosted or alternative providers)</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="fill" class="full-width"
                        *ngIf="showOrganizationId">
          <mat-label>Organization ID (Optional)</mat-label>
          <input matInput formControlName="organization_id"
                 placeholder="org-...">
          <mat-hint>OpenAI organization ID if applicable</mat-hint>
        </mat-form-field>

        <div class="test-section">
          <button mat-stroked-button type="button" color="primary" 
                  (click)="testConnection()"
                  [disabled]="(!form.get('api_key')?.value && !data) || testing">
            <mat-icon *ngIf="!testing">speed</mat-icon>
            <mat-spinner *ngIf="testing" diameter="20" style="display: inline-block; margin-right: 8px;"></mat-spinner>
            {{ testing ? 'Testing...' : 'Test Connection' }}
          </button>
          <span class="test-result" [class.success]="testSuccess" [class.error]="testError">
            {{ testMessage }}
          </span>
        </div>

        <mat-expansion-panel *ngIf="testRequest || testResponse" class="test-details">
          <mat-expansion-panel-header>
            <mat-panel-title>
              <mat-icon>{{ testSuccess ? 'check_circle' : 'error' }}</mat-icon>
              Test Details
            </mat-panel-title>
            <mat-panel-description>
              View request and response details
            </mat-panel-description>
          </mat-expansion-panel-header>
          
          <div class="test-details-content">
            <div *ngIf="testRequest" class="detail-section">
              <h4>Request Sent:</h4>
              <pre>{{ testRequest | json }}</pre>
            </div>
            
            <div *ngIf="testResponse" class="detail-section">
              <h4>Response Received:</h4>
              <pre>{{ testResponse | json }}</pre>
            </div>
          </div>
        </mat-expansion-panel>
      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
      <button mat-raised-button color="primary" 
              [disabled]="!form.valid"
              (click)="onSave()">
        Save
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content {
      padding-top: 20px;
      min-width: 500px;
    }

    .full-width {
      width: 100%;
      margin-bottom: 15px;
    }

    .current-values {
      background: #f5f5f5;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;
      border: 1px solid #e0e0e0;
    }

    .info-box {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
      color: #1976d2;
      font-weight: 500;
    }

    .credential-display {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .field-display {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 0;
    }

    .field-display strong {
      min-width: 100px;
      color: #666;
    }

    .test-section {
      margin: 20px 0;
      padding: 15px;
      background: #f9f9f9;
      border-radius: 4px;
      display: flex;
      align-items: center;
      gap: 15px;
    }

    .test-result {
      font-size: 14px;
    }

    .test-result.success {
      color: #4caf50;
    }

    .test-result.error {
      color: #f44336;
    }

    mat-option mat-icon {
      margin-right: 8px;
      vertical-align: middle;
    }

    .test-details {
      margin-top: 20px;
      background: #f9f9f9;
    }

    .test-details-content {
      padding: 16px;
    }

    .detail-section {
      margin-bottom: 16px;
    }

    .detail-section h4 {
      margin-bottom: 8px;
      color: #666;
      font-size: 14px;
      font-weight: 500;
    }

    .detail-section pre {
      background: #fff;
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      padding: 12px;
      overflow-x: auto;
      font-size: 12px;
      font-family: 'Courier New', monospace;
      margin: 0;
    }

    mat-spinner {
      vertical-align: middle;
    }

    .model-id {
      color: #666;
      font-size: 0.9em;
      font-family: 'Courier New', monospace;
      margin-left: 4px;
    }
  `]
})
export class AICredentialDialogComponent {
  form: FormGroup;
  testing = false;
  testSuccess = false;
  testError = false;
  testMessage = '';
  testRequest: any = null;
  testResponse: any = null;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<AICredentialDialogComponent>,
    private credentialsService: CredentialsService,
    @Inject(MAT_DIALOG_DATA) public data: AICredential | null
  ) {
    this.form = this.fb.group({
      name: [data?.name || '', Validators.required],
      provider: [data?.provider || 'openai', Validators.required],
      api_key: ['', data ? [] : Validators.required],
      model: [data?.model || ''],
      base_url: [data?.base_url || ''],
      organization_id: [data?.organization_id || ''],
      azure_endpoint: [data?.azure_endpoint || ''],
      deployment_name: [data?.deployment_name || ''],
      api_version: [data?.api_version || ''],
    });

    // Watch provider changes to show/hide fields and update validators
    this.form.get('provider')?.valueChanges.subscribe(provider => {
      this.updateFieldVisibility(provider);
    });
    // Apply validators for initial provider value
    this.updateFieldVisibility(data?.provider || 'openai');
  }

  get showAzureFields(): boolean {
    return this.form.get('provider')?.value === 'azure';
  }

  get showBaseUrl(): boolean {
    return this.form.get('provider')?.value === 'custom';
  }

  get showOrganizationId(): boolean {
    return this.form.get('provider')?.value === 'openai';
  }
  
  getModelPlaceholder(): string {
    const provider = this.form.get('provider')?.value;
    switch (provider) {
      case 'openai': return 'e.g., gpt-4-turbo-preview, gpt-4, gpt-3.5-turbo';
      case 'anthropic': return 'e.g., claude-sonnet-4-20250514, claude-3-opus-20240229';
      case 'gemini': return 'e.g., gemini-2.5-pro, gemini-2.0-flash';
      case 'azure': return 'Optional — leave empty to use deployment name';
      default: return 'Enter the model identifier';
    }
  }

  getModelHint(): string {
    const provider = this.form.get('provider')?.value;
    switch (provider) {
      case 'openai': return 'Specify the OpenAI model to use (leave empty for default)';
      case 'anthropic': return 'Specify the Claude model version to use (leave empty for default)';
      case 'gemini': return 'Specify the Gemini model to use (leave empty for default)';
      case 'azure': return 'Optional — the deployment name is used by default';
      default: return 'Enter the specific model identifier for this provider';
    }
  }

  updateFieldVisibility(provider: string) {
    const azureEndpoint = this.form.get('azure_endpoint');
    const deploymentName = this.form.get('deployment_name');

    if (provider === 'azure') {
      azureEndpoint?.setValidators(Validators.required);
      deploymentName?.setValidators(Validators.required);
    } else {
      azureEndpoint?.clearValidators();
      azureEndpoint?.setValue('');
      deploymentName?.clearValidators();
      deploymentName?.setValue('');
      this.form.get('api_version')?.setValue('');
    }
    azureEndpoint?.updateValueAndValidity();
    deploymentName?.updateValueAndValidity();

    if (provider !== 'custom') this.form.get('base_url')?.setValue('');
    if (provider !== 'openai') this.form.get('organization_id')?.setValue('');
  }

  maskApiKey(key: string): string {
    if (!key) return '';
    if (key.length <= 8) return '****';
    return key.substring(0, 4) + '*'.repeat(Math.min(key.length - 8, 20)) + key.substring(key.length - 4);
  }

  testConnection() {
    this.testing = true;
    this.testSuccess = false;
    this.testError = false;
    this.testMessage = 'Testing connection...';
    this.testRequest = null;
    this.testResponse = null;

    const formValue = this.form.value;
    
    // First, we need to save the credential temporarily or use existing one
    if (this.data?.id) {
      // Test existing credential with updated values
      // Only update if a new API key is provided
      if (formValue.api_key) {
        const credentials: any = { api_key: formValue.api_key, model: formValue.model || '' };
        if (formValue.provider === 'azure') {
          credentials['azure_endpoint'] = formValue.azure_endpoint;
          credentials['deployment_name'] = formValue.deployment_name;
          credentials['api_version'] = formValue.api_version || '';
        }
        const updateData = { name: formValue.name, credentials };
        
        this.credentialsService.updateAICredential(this.data.id, updateData).subscribe({
          next: () => {
            // Now test the updated credential
            this.performTest(this.data!.id!);
          },
          error: (error) => {
            this.testing = false;
            this.testSuccess = false;
            this.testError = true;
            this.testMessage = 'Failed to update credential for testing';
            console.error('Update error:', error);
          }
        });
      } else {
        // Test with existing credential (API key is stored server-side)
        this.performTest(this.data.id);
      }
    } else {
      // For new credentials, create temporarily and test
      const newCredential: any = {
        name: formValue.name,
        provider: formValue.provider,
        api_key: formValue.api_key,
        model: formValue.model || '',
      };
      if (formValue.provider === 'azure') {
        newCredential['azure_endpoint'] = formValue.azure_endpoint;
        newCredential['deployment_name'] = formValue.deployment_name;
        newCredential['api_version'] = formValue.api_version || '';
      }
      
      // Create the credential
      this.credentialsService.createAICredential(newCredential).subscribe({
        next: (created) => {
          // Test the created credential
          this.performTest(created.id!);
          // Store the ID for potential deletion if user cancels
          this.temporaryCredId = created.id;
        },
        error: (error) => {
          this.testing = false;
          this.testSuccess = false;
          this.testError = true;
          this.testMessage = 'Failed to create test credential';
          console.error('Create error:', error);
        }
      });
    }
  }

  private temporaryCredId?: string;

  private performTest(credentialId: string) {
    this.credentialsService.testCredential(credentialId).subscribe({
      next: (result) => {
        this.testing = false;
        this.testSuccess = result.success;
        this.testError = !result.success;
        this.testMessage = result.message;
        this.testRequest = result.request;
        this.testResponse = result.response || result.error;
        
        if (result.error) {
          console.error('Test error:', result.error);
        }
      },
      error: (error) => {
        this.testing = false;
        this.testSuccess = false;
        this.testError = true;
        this.testMessage = 'Test failed: Network error';
        this.testResponse = error;
        console.error('Network error:', error);
      }
    });
  }

  onCancel(): void {
    // Clean up temporary credential if created for testing
    if (this.temporaryCredId && !this.data) {
      this.credentialsService.deleteAICredential(this.temporaryCredId).subscribe({
        next: () => console.log('Temporary credential cleaned up'),
        error: (err) => console.error('Failed to clean up temporary credential:', err)
      });
    }
    this.dialogRef.close();
  }

  onSave(): void {
    if (this.form.valid) {
      const formValue = this.form.value;

      const credentialData: any = {
        name: formValue.name,
        provider: formValue.provider,
        model: formValue.model || ''
      };

      if (formValue.api_key) {
        credentialData.api_key = formValue.api_key;
      }

      if (formValue.base_url) {
        credentialData.base_url = formValue.base_url;
      }
      if (formValue.organization_id) {
        credentialData.organization_id = formValue.organization_id;
      }
      if (formValue.provider === 'azure') {
        credentialData.azure_endpoint = formValue.azure_endpoint;
        credentialData.deployment_name = formValue.deployment_name;
        credentialData.api_version = formValue.api_version || '';
      }

      // If a credential was already created during "Test Connection", include its id
      // so the parent updates it rather than attempting a duplicate create.
      if (this.temporaryCredId) {
        credentialData.id = this.temporaryCredId;
        this.temporaryCredId = undefined;
      }

      this.dialogRef.close(credentialData);
    }
  }
}