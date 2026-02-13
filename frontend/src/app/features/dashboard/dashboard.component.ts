import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';
import { JobsService, Job } from '../../core/services/jobs.service';

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
              <p class="stat-number">{{ totalJobs }}</p>
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
              <p class="stat-number">{{ completedJobs }}</p>
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
              <p class="stat-number">{{ runningJobs }}</p>
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
              <p class="stat-number">{{ failedJobs }}</p>
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
          <p *ngIf="recentJobs.length === 0" class="no-data">No recent jobs to display</p>
          <table *ngIf="recentJobs.length > 0" class="jobs-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Output File</th>
                <th>Tickets</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let job of recentJobs">
                <td>
                  <span class="status-badge" [ngClass]="job.status">
                    {{ job.status }}
                  </span>
                </td>
                <td>{{ job.output_filename || '—' }}</td>
                <td>{{ job.tickets_processed }}</td>
                <td>{{ job.created_at | date:'short' }}</td>
                <td>
                  <a mat-button [routerLink]="'/jobs/' + job.id">View</a>
                </td>
              </tr>
            </tbody>
          </table>
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

    .jobs-table {
      width: 100%;
      border-collapse: collapse;

      th, td {
        text-align: left;
        padding: 10px 12px;
        border-bottom: 1px solid #e0e0e0;
      }

      th {
        color: #666;
        font-weight: 500;
        font-size: 13px;
      }
    }

    .status-badge {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      text-transform: capitalize;

      &.completed {
        background: #e8f5e9;
        color: #2e7d32;
      }

      &.running, &.pending {
        background: #fff3e0;
        color: #e65100;
      }

      &.failed {
        background: #fbe9e7;
        color: #c62828;
      }

      &.cancelled {
        background: #f5f5f5;
        color: #757575;
      }
    }
  `]
})
export class DashboardComponent implements OnInit {
  private jobsService = inject(JobsService);

  totalJobs = 0;
  completedJobs = 0;
  runningJobs = 0;
  failedJobs = 0;
  recentJobs: Job[] = [];

  ngOnInit(): void {
    this.jobsService.getJobs().subscribe({
      next: (jobs) => {
        this.totalJobs = jobs.length;
        this.completedJobs = jobs.filter(j => j.status === 'completed').length;
        this.runningJobs = jobs.filter(j => j.status === 'running' || j.status === 'pending').length;
        this.failedJobs = jobs.filter(j => j.status === 'failed').length;
        this.recentJobs = jobs.slice(0, 5);
      }
    });
  }
}
