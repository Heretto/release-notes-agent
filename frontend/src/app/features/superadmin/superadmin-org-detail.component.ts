import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatDividerModule } from '@angular/material/divider';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog.component';
import { SuperadminService, SuperadminOrgDetail } from '../../core/services/superadmin.service';
import { SuperadminAddMemberDialogComponent, AddMemberDialogResult } from './superadmin-add-member-dialog.component';

@Component({
  selector: 'app-superadmin-org-detail',
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
    MatDialogModule,
    MatDividerModule,
  ],
  template: `
    <div class="detail-container">
      <div *ngIf="loading" class="loading-container">
        <mat-spinner diameter="40"></mat-spinner>
      </div>

      <div *ngIf="error" class="error-message">
        <mat-icon>error</mat-icon>
        <span>{{ error }}</span>
        <button mat-button color="primary" (click)="loadOrganization()">Retry</button>
      </div>

      <div *ngIf="!loading && !error && org">
        <div class="page-header">
          <button mat-icon-button (click)="goBack()" matTooltip="Back to organizations">
            <mat-icon>arrow_back</mat-icon>
          </button>
          <div class="header-text">
            <h1>{{ org.name }}</h1>
            <span class="slug">{{ org.slug }}</span>
          </div>
          <span class="spacer"></span>
          <button mat-raised-button color="warn" (click)="confirmDelete()">
            <mat-icon>delete</mat-icon>
            Delete Organization
          </button>
        </div>

        <!-- Stats Cards -->
        <div class="stats-row">
          <mat-card class="stat-card">
            <mat-card-content>
              <div class="stat-value">{{ org.member_count }}</div>
              <div class="stat-label">Members</div>
            </mat-card-content>
          </mat-card>
          <mat-card class="stat-card">
            <mat-card-content>
              <div class="stat-value">{{ org.job_count }}</div>
              <div class="stat-label">Jobs</div>
            </mat-card-content>
          </mat-card>
          <mat-card class="stat-card">
            <mat-card-content>
              <div class="stat-value">{{ org.created_at | date:'mediumDate' }}</div>
              <div class="stat-label">Created</div>
            </mat-card-content>
          </mat-card>
          <mat-card class="stat-card">
            <mat-card-content>
              <div class="stat-value">{{ org.last_activity ? (org.last_activity | date:'mediumDate') : 'None' }}</div>
              <div class="stat-label">Last Activity</div>
            </mat-card-content>
          </mat-card>
        </div>

        <!-- Organization Info -->
        <mat-card class="info-card">
          <mat-card-header>
            <mat-card-title>Organization Details</mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">ID</span>
                <span class="info-value mono">{{ org.id }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Created By</span>
                <span class="info-value">{{ org.created_by_email || 'Unknown' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Status</span>
                <mat-chip [color]="org.is_active ? 'primary' : 'warn'" selected>
                  {{ org.is_active ? 'Active' : 'Inactive' }}
                </mat-chip>
              </div>
              <div class="info-item" *ngIf="org.updated_at">
                <span class="info-label">Last Updated</span>
                <span class="info-value">{{ org.updated_at | date:'medium' }}</span>
              </div>
            </div>
          </mat-card-content>
        </mat-card>

        <!-- Members Table -->
        <mat-card>
          <mat-card-header>
            <mat-card-title>Members</mat-card-title>
            <mat-card-subtitle>{{ org.members.length }} members in this organization</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <div class="members-actions">
              <button mat-raised-button color="primary" (click)="openAddMemberDialog()">
                <mat-icon>person_add</mat-icon>
                Add Member
              </button>
            </div>

            <table mat-table [dataSource]="org.members" class="members-table" *ngIf="org.members.length > 0">
              <ng-container matColumnDef="email">
                <th mat-header-cell *matHeaderCellDef>Email</th>
                <td mat-cell *matCellDef="let member">{{ member.email }}</td>
              </ng-container>

              <ng-container matColumnDef="role">
                <th mat-header-cell *matHeaderCellDef>Role</th>
                <td mat-cell *matCellDef="let member">
                  <mat-chip [color]="member.role === 'admin' ? 'accent' : 'primary'" selected>
                    {{ member.role }}
                  </mat-chip>
                </td>
              </ng-container>

              <ng-container matColumnDef="status">
                <th mat-header-cell *matHeaderCellDef>Status</th>
                <td mat-cell *matCellDef="let member">
                  <span [class.active-status]="member.is_active" [class.inactive-status]="!member.is_active">
                    {{ member.is_active ? 'Active' : 'Inactive' }}
                  </span>
                </td>
              </ng-container>

              <ng-container matColumnDef="joined_at">
                <th mat-header-cell *matHeaderCellDef>Joined</th>
                <td mat-cell *matCellDef="let member">
                  {{ member.joined_at ? (member.joined_at | date:'mediumDate') : '—' }}
                </td>
              </ng-container>

              <ng-container matColumnDef="actions">
                <th mat-header-cell *matHeaderCellDef></th>
                <td mat-cell *matCellDef="let member">
                  <button mat-icon-button color="warn"
                          (click)="confirmRemoveMember(member); $event.stopPropagation()"
                          matTooltip="Remove from organization">
                    <mat-icon>person_remove</mat-icon>
                  </button>
                </td>
              </ng-container>

              <tr mat-header-row *matHeaderRowDef="memberColumns"></tr>
              <tr mat-row *matRowDef="let row; columns: memberColumns;"></tr>
            </table>

            <div *ngIf="org.members.length === 0" class="empty-state">
              <mat-icon>people</mat-icon>
              <p>No members in this organization</p>
            </div>
          </mat-card-content>
        </mat-card>
      </div>
    </div>
  `,
  styles: [`
    .detail-container {
      max-width: 1200px;
      margin: 0 auto;
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

    .page-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
    }

    .header-text h1 {
      margin: 0;
      font-size: 28px;
      font-weight: 400;
    }

    .slug {
      font-size: 13px;
      color: rgba(0, 0, 0, 0.54);
    }

    .spacer {
      flex: 1 1 auto;
    }

    .stats-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }

    .stat-card {
      text-align: center;
    }

    .stat-value {
      font-size: 24px;
      font-weight: 500;
      margin-bottom: 4px;
    }

    .stat-label {
      font-size: 13px;
      color: rgba(0, 0, 0, 0.54);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .info-card {
      margin-bottom: 24px;
    }

    .info-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
      padding-top: 8px;
    }

    .info-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .info-label {
      font-size: 12px;
      color: rgba(0, 0, 0, 0.54);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .info-value {
      font-size: 14px;
    }

    .mono {
      font-family: monospace;
      font-size: 13px;
    }

    .members-actions {
      margin-bottom: 16px;
    }

    .members-table {
      width: 100%;
    }

    .active-status {
      color: #4caf50;
    }

    .inactive-status {
      color: #f44336;
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

    @media (max-width: 768px) {
      .stats-row {
        grid-template-columns: repeat(2, 1fr);
      }

      .info-grid {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class SuperadminOrgDetailComponent implements OnInit {
  private superadminService = inject(SuperadminService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private snackBar = inject(MatSnackBar);
  private dialog = inject(MatDialog);

  org: SuperadminOrgDetail | null = null;
  loading = true;
  error: string | null = null;
  memberColumns = ['email', 'role', 'status', 'joined_at', 'actions'];

  ngOnInit() {
    this.loadOrganization();
  }

  loadOrganization() {
    const orgId = this.route.snapshot.paramMap.get('id');
    if (!orgId) {
      this.error = 'No organization ID provided';
      this.loading = false;
      return;
    }

    this.loading = true;
    this.error = null;
    this.superadminService.getOrganization(orgId).subscribe({
      next: (org) => {
        this.org = org;
        this.loading = false;
      },
      error: (err) => {
        this.error = err.status === 404
          ? 'Organization not found.'
          : 'Failed to load organization details.';
        this.loading = false;
      }
    });
  }

  goBack() {
    this.router.navigate(['/superadmin']);
  }

  openAddMemberDialog() {
    if (!this.org) return;

    const dialogRef = this.dialog.open(SuperadminAddMemberDialogComponent, {
      data: { orgName: this.org.name }
    });

    dialogRef.afterClosed().subscribe((result: AddMemberDialogResult | undefined) => {
      if (!result || !this.org) return;

      if (result.mode === 'add') {
        this.superadminService.addMember(this.org.id, result.email, result.role).subscribe({
          next: (res) => {
            this.snackBar.open(res.message, 'OK', { duration: 3000 });
            this.loadOrganization();
          },
          error: (err) => {
            this.snackBar.open(
              err.error?.detail || 'Failed to add member',
              'OK',
              { duration: 5000 }
            );
          }
        });
      } else {
        this.superadminService.inviteUser(this.org.id, result.email, result.role).subscribe({
          next: (invitation) => {
            const inviteUrl = `${window.location.origin}/invite/${invitation.token}`;
            this.snackBar.open('Invitation created. Copy the link to share.', 'Copy Link', { duration: 10000 })
              .onAction().subscribe(() => {
                navigator.clipboard.writeText(inviteUrl);
                this.snackBar.open('Invitation link copied!', 'OK', { duration: 2000 });
              });
          },
          error: (err) => {
            this.snackBar.open(
              err.error?.detail || 'Failed to send invitation',
              'OK',
              { duration: 5000 }
            );
          }
        });
      }
    });
  }

  confirmRemoveMember(member: { user_id: string; email: string }) {
    if (!this.org) return;

    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Remove Member',
        message: `Remove "${member.email}" from "${this.org.name}"? They will lose access to this organization's resources.`,
        confirmText: 'Remove'
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed && this.org) {
        this.superadminService.removeMember(this.org.id, member.user_id).subscribe({
          next: (res) => {
            this.snackBar.open(res.message, 'OK', { duration: 3000 });
            this.loadOrganization();
          },
          error: (err) => {
            this.snackBar.open(
              err.error?.detail || 'Failed to remove member',
              'OK',
              { duration: 5000 }
            );
          }
        });
      }
    });
  }

  confirmDelete() {
    if (!this.org) return;

    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete Organization',
        message: `Are you sure you want to delete "${this.org.name}"? This will remove all associated data including members, jobs, credentials, and instruction sets. This action cannot be undone.`,
        confirmText: 'Delete'
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed && this.org) {
        this.superadminService.deleteOrganization(this.org.id).subscribe({
          next: (res) => {
            this.snackBar.open(res.message, 'OK', { duration: 3000 });
            this.router.navigate(['/superadmin']);
          },
          error: (err) => {
            this.snackBar.open(
              err.error?.detail || 'Failed to delete organization',
              'OK',
              { duration: 5000 }
            );
          }
        });
      }
    });
  }
}
