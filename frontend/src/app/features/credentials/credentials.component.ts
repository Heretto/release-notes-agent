import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTableModule } from '@angular/material/table';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { 
  CredentialsService, 
  JiraCredential, 
  HerettoCredential, 
  AICredential 
} from '../../core/services/credentials.service';
import { JiraCredentialDialogComponent } from './jira-credential-dialog.component';
import { AICredentialDialogComponent } from './ai-credential-dialog.component';
import { TestResultsDialogComponent } from './test-results-dialog.component';

@Component({
  selector: 'app-credentials',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    MatTableModule,
    MatDialogModule,
    MatSnackBarModule,
    MatProgressSpinnerModule
  ],
  template: `
    <div class="credentials-container">
      <h1>Credentials Management</h1>
      
      <mat-card>
        <mat-card-content>
          <mat-tab-group>
            <mat-tab label="Jira">
              <div class="tab-content">
                <div class="header-row">
                  <h3>Jira Credentials</h3>
                  <button mat-raised-button color="primary" (click)="addJiraCredential()">
                    <mat-icon>add</mat-icon>
                    Add Jira Credentials
                  </button>
                </div>

                <div *ngIf="loadingJira" class="loading-container">
                  <mat-spinner></mat-spinner>
                </div>

                <table mat-table [dataSource]="jiraCredentials" class="full-width" *ngIf="!loadingJira">
                  <ng-container matColumnDef="name">
                    <th mat-header-cell *matHeaderCellDef>Name</th>
                    <td mat-cell *matCellDef="let element">{{ element.name }}</td>
                  </ng-container>

                  <ng-container matColumnDef="server_url">
                    <th mat-header-cell *matHeaderCellDef>Server URL</th>
                    <td mat-cell *matCellDef="let element">{{ element.server_url }}</td>
                  </ng-container>

                  <ng-container matColumnDef="email">
                    <th mat-header-cell *matHeaderCellDef>Email</th>
                    <td mat-cell *matCellDef="let element">{{ element.email }}</td>
                  </ng-container>

                  <ng-container matColumnDef="actions">
                    <th mat-header-cell *matHeaderCellDef>Actions</th>
                    <td mat-cell *matCellDef="let element">
                      <button mat-icon-button color="accent" 
                              (click)="testJiraCredential(element)"
                              matTooltip="Test Connection"
                              [disabled]="testingCredential === element.id">
                        <mat-icon *ngIf="testingCredential !== element.id">speed</mat-icon>
                        <mat-spinner *ngIf="testingCredential === element.id" 
                                     diameter="20"></mat-spinner>
                      </button>
                      <button mat-icon-button color="primary" 
                              (click)="editJiraCredential(element)"
                              matTooltip="Edit">
                        <mat-icon>edit</mat-icon>
                      </button>
                      <button mat-icon-button color="warn" 
                              (click)="deleteJiraCredential(element)"
                              matTooltip="Delete">
                        <mat-icon>delete</mat-icon>
                      </button>
                    </td>
                  </ng-container>

                  <tr mat-header-row *matHeaderRowDef="jiraColumns"></tr>
                  <tr mat-row *matRowDef="let row; columns: jiraColumns;"></tr>
                </table>

                <p *ngIf="jiraCredentials.length === 0 && !loadingJira" class="no-data">
                  No Jira credentials configured. Click "Add Jira Credentials" to get started.
                </p>
              </div>
            </mat-tab>
            
            <mat-tab label="Heretto">
              <div class="tab-content">
                <div class="header-row">
                  <h3>Heretto CCMS Credentials</h3>
                  <button mat-raised-button color="primary" (click)="addHerettoCredential()">
                    <mat-icon>add</mat-icon>
                    Add Heretto Credentials
                  </button>
                </div>
                <p class="no-data">No Heretto credentials configured.</p>
              </div>
            </mat-tab>
            
            <mat-tab label="AI Providers">
              <div class="tab-content">
                <div class="header-row">
                  <h3>AI Provider Credentials</h3>
                  <button mat-raised-button color="primary" (click)="addAICredential()">
                    <mat-icon>add</mat-icon>
                    Add AI Credentials
                  </button>
                </div>

                <div *ngIf="loadingAI" class="loading-container">
                  <mat-spinner></mat-spinner>
                </div>

                <table mat-table [dataSource]="aiCredentials" class="full-width" *ngIf="!loadingAI && aiCredentials.length > 0">
                  <ng-container matColumnDef="name">
                    <th mat-header-cell *matHeaderCellDef>Name</th>
                    <td mat-cell *matCellDef="let element">{{ element.name }}</td>
                  </ng-container>

                  <ng-container matColumnDef="provider">
                    <th mat-header-cell *matHeaderCellDef>Provider</th>
                    <td mat-cell *matCellDef="let element">
                      <span class="provider-badge">{{ formatProvider(element.provider) }}</span>
                    </td>
                  </ng-container>

                  <ng-container matColumnDef="model">
                    <th mat-header-cell *matHeaderCellDef>Model</th>
                    <td mat-cell *matCellDef="let element">{{ element.model || 'Default' }}</td>
                  </ng-container>

                  <ng-container matColumnDef="actions">
                    <th mat-header-cell *matHeaderCellDef>Actions</th>
                    <td mat-cell *matCellDef="let element">
                      <button mat-icon-button color="accent" 
                              (click)="testAICredential(element)"
                              matTooltip="Test Connection"
                              [disabled]="testingCredential === element.id">
                        <mat-icon *ngIf="testingCredential !== element.id">speed</mat-icon>
                        <mat-spinner *ngIf="testingCredential === element.id" 
                                     diameter="20"></mat-spinner>
                      </button>
                      <button mat-icon-button color="primary" 
                              (click)="editAICredential(element)"
                              matTooltip="Edit">
                        <mat-icon>edit</mat-icon>
                      </button>
                      <button mat-icon-button color="warn" 
                              (click)="deleteAICredential(element)"
                              matTooltip="Delete">
                        <mat-icon>delete</mat-icon>
                      </button>
                    </td>
                  </ng-container>

                  <tr mat-header-row *matHeaderRowDef="aiColumns"></tr>
                  <tr mat-row *matRowDef="let row; columns: aiColumns;"></tr>
                </table>

                <p *ngIf="aiCredentials.length === 0 && !loadingAI" class="no-data">
                  No AI provider credentials configured. Click "Add AI Credentials" to get started.
                </p>
              </div>
            </mat-tab>
          </mat-tab-group>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .credentials-container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
    }
    
    .tab-content {
      padding: 20px;
    }

    .header-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }

    .header-row h3 {
      margin: 0;
    }

    .full-width {
      width: 100%;
    }

    .no-data {
      text-align: center;
      color: #666;
      padding: 40px;
      background: #f5f5f5;
      border-radius: 4px;
    }

    .loading-container {
      display: flex;
      justify-content: center;
      padding: 40px;
    }

    .provider-badge {
      padding: 4px 8px;
      border-radius: 4px;
      background: #e3f2fd;
      color: #1976d2;
      font-size: 12px;
      text-transform: uppercase;
      font-weight: 500;
    }
  `]
})
export class CredentialsComponent implements OnInit {
  private credentialsService = inject(CredentialsService);
  private dialog = inject(MatDialog);
  private snackBar = inject(MatSnackBar);

  jiraCredentials: JiraCredential[] = [];
  herettoCredentials: HerettoCredential[] = [];
  aiCredentials: AICredential[] = [];

  loadingJira = false;
  loadingHeretto = false;
  loadingAI = false;
  testingCredential: string | null = null;

  jiraColumns: string[] = ['name', 'server_url', 'email', 'actions'];
  aiColumns: string[] = ['name', 'provider', 'model', 'actions'];

  ngOnInit() {
    this.loadJiraCredentials();
    this.loadAICredentials();
  }

  loadJiraCredentials() {
    this.loadingJira = true;
    this.credentialsService.getJiraCredentials().subscribe({
      next: (credentials) => {
        this.jiraCredentials = credentials;
        this.loadingJira = false;
      },
      error: (error) => {
        console.error('Failed to load Jira credentials:', error);
        this.loadingJira = false;
      }
    });
  }

  addJiraCredential() {
    const dialogRef = this.dialog.open(JiraCredentialDialogComponent, {
      width: '500px',
      data: null
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.credentialsService.createJiraCredential(result).subscribe({
          next: (credential) => {
            // Create a new array reference to trigger change detection
            this.jiraCredentials = [...this.jiraCredentials, credential];
            this.snackBar.open('Jira credential added successfully', 'Close', {
              duration: 3000
            });
          },
          error: (error) => {
            this.snackBar.open('Failed to add Jira credential', 'Close', {
              duration: 3000
            });
            console.error('Error adding credential:', error);
          }
        });
      }
    });
  }

  editJiraCredential(credential: JiraCredential) {
    const dialogRef = this.dialog.open(JiraCredentialDialogComponent, {
      width: '500px',
      data: credential
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result && credential.id) {
        this.credentialsService.updateJiraCredential(credential.id, result).subscribe({
          next: (updated) => {
            const index = this.jiraCredentials.findIndex(c => c.id === credential.id);
            if (index >= 0) {
              // Create a new array reference to trigger change detection
              this.jiraCredentials = [
                ...this.jiraCredentials.slice(0, index),
                updated,
                ...this.jiraCredentials.slice(index + 1)
              ];
            }
            this.snackBar.open('Jira credential updated successfully', 'Close', {
              duration: 3000
            });
          },
          error: (error) => {
            this.snackBar.open('Failed to update Jira credential', 'Close', {
              duration: 3000
            });
            console.error('Error updating credential:', error);
          }
        });
      }
    });
  }

  deleteJiraCredential(credential: JiraCredential) {
    if (credential.id && confirm(`Are you sure you want to delete "${credential.name}"?`)) {
      this.credentialsService.deleteJiraCredential(credential.id).subscribe({
        next: () => {
          this.jiraCredentials = this.jiraCredentials.filter(c => c.id !== credential.id);
          this.snackBar.open('Jira credential deleted successfully', 'Close', {
            duration: 3000
          });
        },
        error: (error) => {
          this.snackBar.open('Failed to delete Jira credential', 'Close', {
            duration: 3000
          });
          console.error('Error deleting credential:', error);
        }
      });
    }
  }

  testJiraCredential(credential: JiraCredential) {
    if (!credential.id) {
      this.snackBar.open('Invalid credential ID', 'Close', { duration: 3000 });
      return;
    }

    this.testingCredential = credential.id;
    this.credentialsService.testCredential(credential.id).subscribe({
      next: (result) => {
        this.testingCredential = null;
        
        // Open dialog to show test results
        const dialogRef = this.dialog.open(TestResultsDialogComponent, {
          width: '700px',
          maxHeight: '80vh',
          data: result
        });
      },
      error: (error) => {
        this.testingCredential = null;
        
        // Show error in dialog
        const dialogRef = this.dialog.open(TestResultsDialogComponent, {
          width: '700px',
          maxHeight: '80vh',
          data: {
            success: false,
            status_code: error.status || 500,
            message: 'Failed to test credential',
            error_details: error.message || 'Unknown error occurred',
            timestamp: new Date().toISOString()
          }
        });
      }
    });
  }

  addHerettoCredential() {
    this.snackBar.open('Heretto credential dialog coming soon', 'Close', {
      duration: 3000
    });
  }

  loadAICredentials() {
    this.loadingAI = true;
    this.credentialsService.getAICredentials().subscribe({
      next: (credentials) => {
        this.aiCredentials = credentials;
        this.loadingAI = false;
      },
      error: (error) => {
        console.error('Failed to load AI credentials:', error);
        this.loadingAI = false;
      }
    });
  }

  addAICredential() {
    const dialogRef = this.dialog.open(AICredentialDialogComponent, {
      width: '600px',
      data: null
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.credentialsService.createAICredential(result).subscribe({
          next: (credential) => {
            // Create a new array reference to trigger change detection
            this.aiCredentials = [...this.aiCredentials, credential];
            this.snackBar.open('AI credential added successfully', 'Close', {
              duration: 3000
            });
          },
          error: (error) => {
            this.snackBar.open('Failed to add AI credential', 'Close', {
              duration: 3000
            });
            console.error('Error adding credential:', error);
          }
        });
      }
    });
  }

  editAICredential(credential: any) {
    // Fetch full credential details first
    this.credentialsService.getAICredential(credential.id).subscribe({
      next: (fullCredential) => {
        const dialogRef = this.dialog.open(AICredentialDialogComponent, {
          width: '600px',
          data: fullCredential
        });

        dialogRef.afterClosed().subscribe(result => {
          if (result && credential.id) {
            this.credentialsService.updateAICredential(credential.id, result).subscribe({
              next: (updated) => {
                const index = this.aiCredentials.findIndex(c => c.id === credential.id);
                if (index >= 0) {
                  // Create a new array reference to trigger change detection
                  this.aiCredentials = [
                    ...this.aiCredentials.slice(0, index),
                    updated,
                    ...this.aiCredentials.slice(index + 1)
                  ];
                }
                this.snackBar.open('AI credential updated successfully', 'Close', {
                  duration: 3000
                });
              },
              error: (error) => {
                this.snackBar.open('Failed to update AI credential', 'Close', {
                  duration: 3000
                });
                console.error('Error updating credential:', error);
              }
            });
          }
        });
      },
      error: (error) => {
        this.snackBar.open('Failed to load credential details', 'Close', {
          duration: 3000
        });
        console.error('Error loading credential:', error);
      }
    });
  }

  deleteAICredential(credential: any) {
    if (credential.id && confirm(`Are you sure you want to delete "${credential.name}"?`)) {
      this.credentialsService.deleteAICredential(credential.id).subscribe({
        next: () => {
          this.aiCredentials = this.aiCredentials.filter(c => c.id !== credential.id);
          this.snackBar.open('AI credential deleted successfully', 'Close', {
            duration: 3000
          });
        },
        error: (error) => {
          this.snackBar.open('Failed to delete AI credential', 'Close', {
            duration: 3000
          });
          console.error('Error deleting credential:', error);
        }
      });
    }
  }

  testAICredential(credential: any) {
    if (!credential.id) {
      this.snackBar.open('Invalid credential ID', 'Close', { duration: 3000 });
      return;
    }

    this.testingCredential = credential.id;
    this.credentialsService.testCredential(credential.id).subscribe({
      next: (result) => {
        this.testingCredential = null;
        
        // Open dialog to show test results
        const dialogRef = this.dialog.open(TestResultsDialogComponent, {
          width: '700px',
          maxHeight: '80vh',
          data: result
        });
      },
      error: (error) => {
        this.testingCredential = null;
        
        // Show error in dialog
        const dialogRef = this.dialog.open(TestResultsDialogComponent, {
          width: '700px',
          maxHeight: '80vh',
          data: {
            success: false,
            status_code: error.status || 500,
            message: 'Failed to test AI credential',
            error_details: error.message || 'Unknown error occurred',
            timestamp: new Date().toISOString()
          }
        });
      }
    });
  }

  formatProvider(provider: string): string {
    const providerMap: { [key: string]: string } = {
      'openai': 'OpenAI',
      'anthropic': 'Anthropic',
      'gemini': 'Google AI',
      'google': 'Google AI',
      'custom': 'Custom'
    };
    return providerMap[provider] || provider;
  }
}