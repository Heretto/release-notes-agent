import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatSlideToggleModule
  ],
  template: `
    <div class="settings-container">
      <h1>Settings</h1>
      
      <mat-card>
        <mat-card-header>
          <mat-card-title>Webhook Configuration</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <p>Configure webhook endpoints for automated job triggering.</p>
          <button mat-stroked-button>
            <mat-icon>settings</mat-icon>
            Configure Webhooks
          </button>
        </mat-card-content>
      </mat-card>
      
      <mat-card>
        <mat-card-header>
          <mat-card-title>AI Model Settings</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <p>Select and configure AI models for content generation.</p>
          <button mat-stroked-button>
            <mat-icon>smart_toy</mat-icon>
            Configure AI Models
          </button>
        </mat-card-content>
      </mat-card>
      
      <mat-card>
        <mat-card-header>
          <mat-card-title>Notifications</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <mat-slide-toggle>Email notifications for job completion</mat-slide-toggle>
          <br><br>
          <mat-slide-toggle>Email notifications for job failures</mat-slide-toggle>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .settings-container {
      max-width: 800px;
      margin: 0 auto;
    }
    
    mat-card {
      margin-bottom: 20px;
    }
  `]
})
export class SettingsComponent {}