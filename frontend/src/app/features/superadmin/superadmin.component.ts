import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { SuperadminService, SuperadminOrgListItem } from '../../core/services/superadmin.service';

@Component({
  selector: 'app-superadmin',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatChipsModule,
    MatTooltipModule,
    MatSnackBarModule,
  ],
  template: `
    <div class="superadmin-container">
      <div class="page-header">
        <h1>System Administration</h1>
        <p class="subtitle">Manage all organizations across the platform</p>
      </div>

      <mat-card>
        <mat-card-header>
          <mat-card-title>Organizations</mat-card-title>
          <mat-card-subtitle>{{ organizations.length }} total organizations</mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <div *ngIf="loading" class="loading-container">
            <mat-spinner diameter="40"></mat-spinner>
          </div>

          <div *ngIf="error" class="error-message">
            <mat-icon>error</mat-icon>
            <span>{{ error }}</span>
            <button mat-button color="primary" (click)="loadOrganizations()">Retry</button>
          </div>

          <table mat-table [dataSource]="organizations" class="org-table" *ngIf="!loading && !error">
            <ng-container matColumnDef="name">
              <th mat-header-cell *matHeaderCellDef>Organization</th>
              <td mat-cell *matCellDef="let org">
                <div class="org-name-cell">
                  <strong>{{ org.name }}</strong>
                  <span class="slug">{{ org.slug }}</span>
                </div>
              </td>
            </ng-container>

            <ng-container matColumnDef="created_by">
              <th mat-header-cell *matHeaderCellDef>Created By</th>
              <td mat-cell *matCellDef="let org">{{ org.created_by_email || '—' }}</td>
            </ng-container>

            <ng-container matColumnDef="members">
              <th mat-header-cell *matHeaderCellDef>Members</th>
              <td mat-cell *matCellDef="let org">
                <mat-chip>{{ org.member_count }}</mat-chip>
              </td>
            </ng-container>

            <ng-container matColumnDef="last_activity">
              <th mat-header-cell *matHeaderCellDef>Last Activity</th>
              <td mat-cell *matCellDef="let org">
                <span *ngIf="org.last_activity" [matTooltip]="(org.last_activity | date:'medium') || ''">
                  {{ getRelativeTime(org.last_activity) }}
                </span>
                <span *ngIf="!org.last_activity" class="no-activity">No activity</span>
              </td>
            </ng-container>

            <ng-container matColumnDef="created_at">
              <th mat-header-cell *matHeaderCellDef>Created</th>
              <td mat-cell *matCellDef="let org">{{ org.created_at | date:'mediumDate' }}</td>
            </ng-container>

            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef></th>
              <td mat-cell *matCellDef="let org">
                <button mat-icon-button color="primary" (click)="viewOrganization(org)"
                        matTooltip="View details">
                  <mat-icon>visibility</mat-icon>
                </button>
              </td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: displayedColumns;"
                class="org-row" (click)="viewOrganization(row)"></tr>
          </table>

          <div *ngIf="!loading && !error && organizations.length === 0" class="empty-state">
            <mat-icon>business</mat-icon>
            <p>No organizations found</p>
          </div>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .superadmin-container {
      max-width: 1200px;
      margin: 0 auto;
    }

    .page-header {
      margin-bottom: 24px;
    }

    .page-header h1 {
      margin: 0;
      font-size: 28px;
      font-weight: 400;
    }

    .subtitle {
      margin: 4px 0 0;
      color: rgba(0, 0, 0, 0.54);
    }

    .loading-container {
      display: flex;
      justify-content: center;
      padding: 40px;
    }

    .error-message {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 16px;
      color: #f44336;
    }

    .org-table {
      width: 100%;
    }

    .org-row {
      cursor: pointer;
    }

    .org-row:hover {
      background-color: rgba(0, 0, 0, 0.04);
    }

    .org-name-cell {
      display: flex;
      flex-direction: column;
    }

    .slug {
      font-size: 12px;
      color: rgba(0, 0, 0, 0.54);
    }

    .no-activity {
      color: rgba(0, 0, 0, 0.38);
      font-style: italic;
    }

    .empty-state {
      text-align: center;
      padding: 40px;
      color: rgba(0, 0, 0, 0.38);
    }

    .empty-state mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
    }
  `]
})
export class SuperadminComponent implements OnInit {
  private superadminService = inject(SuperadminService);
  private router = inject(Router);
  private snackBar = inject(MatSnackBar);

  organizations: SuperadminOrgListItem[] = [];
  loading = true;
  error: string | null = null;
  displayedColumns = ['name', 'created_by', 'members', 'last_activity', 'created_at', 'actions'];

  ngOnInit() {
    this.loadOrganizations();
  }

  loadOrganizations() {
    this.loading = true;
    this.error = null;
    this.superadminService.listOrganizations().subscribe({
      next: (orgs) => {
        this.organizations = orgs;
        this.loading = false;
      },
      error: (err) => {
        this.error = err.status === 403
          ? 'You do not have permission to access this page.'
          : 'Failed to load organizations.';
        this.loading = false;
      }
    });
  }

  viewOrganization(org: SuperadminOrgListItem) {
    this.router.navigate(['/superadmin', org.id]);
  }

  getRelativeTime(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 30) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  }
}
