import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    RouterLink
  ],
  template: `
    <div class="dashboard-container">
      <h1>Dashboard</h1>
      
      <div class="stats-grid">
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon">
              <mat-icon>work</mat-icon>
            </div>
            <div class="stat-content">
              <h3>Total Jobs</h3>
              <p class="stat-number">0</p>
            </div>
          </mat-card-content>
        </mat-card>
        
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon success">
              <mat-icon>check_circle</mat-icon>
            </div>
            <div class="stat-content">
              <h3>Completed</h3>
              <p class="stat-number">0</p>
            </div>
          </mat-card-content>
        </mat-card>
        
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon warning">
              <mat-icon>schedule</mat-icon>
            </div>
            <div class="stat-content">
              <h3>Running</h3>
              <p class="stat-number">0</p>
            </div>
          </mat-card-content>
        </mat-card>
        
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon error">
              <mat-icon>error</mat-icon>
            </div>
            <div class="stat-content">
              <h3>Failed</h3>
              <p class="stat-number">0</p>
            </div>
          </mat-card-content>
        </mat-card>
      </div>
      
      <div class="actions-section">
        <h2>Quick Actions</h2>
        <div class="action-buttons">
          <button mat-raised-button color="primary" routerLink="/jobs">
            <mat-icon>add</mat-icon>
            Create New Job
          </button>
          
          <button mat-raised-button routerLink="/credentials">
            <mat-icon>vpn_key</mat-icon>
            Manage Credentials
          </button>
          
          <button mat-raised-button routerLink="/instructions">
            <mat-icon>description</mat-icon>
            Configure Instructions
          </button>
        </div>
      </div>
      
      <mat-card class="recent-jobs">
        <mat-card-header>
          <mat-card-title>Recent Jobs</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <p class="no-data">No recent jobs to display</p>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .dashboard-container {
      max-width: 1200px;
      margin: 0 auto;
    }
    
    h1 {
      margin-bottom: 30px;
    }
    
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 20px;
      margin-bottom: 40px;
    }
    
    .stat-card {
      .mat-mdc-card-content {
        display: flex;
        align-items: center;
        padding: 20px !important;
      }
    }
    
    .stat-icon {
      font-size: 48px;
      margin-right: 20px;
      color: #3f51b5;
      
      &.success {
        color: #4caf50;
      }
      
      &.warning {
        color: #ff9800;
      }
      
      &.error {
        color: #f44336;
      }
      
      mat-icon {
        font-size: 48px;
        height: 48px;
        width: 48px;
      }
    }
    
    .stat-content {
      h3 {
        margin: 0;
        color: #666;
        font-size: 14px;
      }
      
      .stat-number {
        margin: 5px 0 0 0;
        font-size: 32px;
        font-weight: bold;
      }
    }
    
    .actions-section {
      margin-bottom: 40px;
      
      h2 {
        margin-bottom: 20px;
      }
    }
    
    .action-buttons {
      display: flex;
      gap: 15px;
      
      button {
        mat-icon {
          margin-right: 8px;
        }
      }
    }
    
    .recent-jobs {
      .no-data {
        text-align: center;
        color: #999;
        padding: 40px 0;
      }
    }
  `]
})
export class DashboardComponent {}