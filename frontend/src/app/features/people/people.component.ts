import { Component, OnInit, inject, ChangeDetectionStrategy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HopOrganizationService } from '@heretto/hop-ui';
import { AppRole, PeopleService, Person } from '../../core/services/people.service';

/**
 * Who is in the organization and what this app lets them do.
 *
 * Separate from hop-core's Administration page, which owns membership and the organization
 * role (admin/member). This owns the app role (author/reviewer) — see
 * backend/app/services/app_roles.py for why the two are different things.
 */
@Component({
  selector: 'app-people',
  standalone: true,
  imports: [
    FormsModule, MatButtonModule, MatCardModule, MatIconModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatTooltipModule, MatProgressSpinnerModule
  ],
  template: `
    <div class="hop-page">
      <div class="hop-page-head">
        <div>
          <h1>People</h1>
          <p class="muted">
            Authors write and run releases. Reviewers can only read release notes and comment
            on them — which is what anyone who signs in on their own starts as.
          </p>
        </div>
      </div>

      <mat-card class="invite-card">
        <h2>Invite someone</h2>
        <p class="muted">
          Choose what they will be able to do, then send the invitation. The role waits on the
          address until they accept.
        </p>
        <div class="invite-row">
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Email address</mat-label>
            <input matInput [(ngModel)]="inviteEmail" type="email" placeholder="colleague@example.com">
          </mat-form-field>
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>They can</mat-label>
            <mat-select [(ngModel)]="inviteRole">
              <mat-option value="author">Write release notes (author)</mat-option>
              <mat-option value="reviewer">Review only</mat-option>
            </mat-select>
          </mat-form-field>
          <button mat-flat-button color="primary" (click)="invite()"
                  [disabled]="!inviteEmail.trim() || working">
            <mat-icon>send</mat-icon> Send invitation
          </button>
        </div>
      </mat-card>

      @if (loading) {
        <div class="loading"><mat-spinner diameter="28"></mat-spinner></div>
      } @else {
        <mat-card>
          <table class="people">
            <thead>
              <tr><th>Email</th><th>Organization</th><th class="role-col">In this app</th></tr>
            </thead>
            <tbody>
              @for (person of people; track person.email) {
                <tr [class.pending]="person.invited">
                  <td>
                    <span class="avatar">{{ initialsOf(person.email) }}</span>
                    <span class="email">{{ person.email }}</span>
                    @if (person.invited) { <span class="tag">Invited</span> }
                  </td>
                  <td class="muted">{{ person.org_role === 'admin' ? 'Administrator' : person.invited ? '—' : 'Member' }}</td>
                  <td class="role-col">
                    <mat-form-field appearance="outline" subscriptSizing="dynamic" class="role-field">
                      <mat-select [value]="person.role" (selectionChange)="setRole(person, $event.value)"
                                  [disabled]="working || isMe(person)"
                                  [matTooltip]="isMe(person) ? 'You cannot change your own role' : ''">
                        <mat-option value="author">Author</mat-option>
                        <mat-option value="reviewer">Reviewer</mat-option>
                      </mat-select>
                    </mat-form-field>
                  </td>
                </tr>
              } @empty {
                <tr><td colspan="3" class="muted">Nobody here yet.</td></tr>
              }
            </tbody>
          </table>
        </mat-card>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    .hop-page-head { margin-bottom: 20px; }
    h1 { margin: 0 0 4px; font-size: 24px; }
    h2 { margin: 0 0 4px; font-size: 16px; }
    .muted { color: var(--text-secondary); font-size: 13px; margin: 0; max-width: 70ch; line-height: 1.55; }
    .loading { display: flex; justify-content: center; padding: 40px; }
    .invite-card { margin-bottom: 20px; padding: 20px; }
    .invite-row { display: flex; gap: 12px; align-items: flex-start; margin-top: 14px; flex-wrap: wrap; }
    .invite-row mat-form-field { flex: 1; min-width: 220px; }
    .invite-row button { height: 56px; }
    .people { width: 100%; border-collapse: collapse; }
    .people th { text-align: left; font-size: 11px; font-weight: 600; letter-spacing: 0.05em;
      text-transform: uppercase; color: var(--text-tertiary); padding: 0 12px 10px; }
    .people td { padding: 10px 12px; border-top: 1px solid var(--border-light); vertical-align: middle; }
    .people tr.pending .email { color: var(--text-secondary); }
    .avatar { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px;
      border-radius: 50%; background: var(--bg-secondary); font-size: 11px; font-weight: 600;
      margin-right: 10px; vertical-align: middle; }
    .email { font-size: 14px; }
    .tag { margin-left: 8px; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px;
      background: var(--bg-secondary); color: var(--text-secondary); }
    .role-col { width: 190px; }
    .role-field { width: 100%; }
  `]
})
export class PeopleComponent implements OnInit {
  private peopleService = inject(PeopleService);
  private organizationService = inject(HopOrganizationService);
  private snackBar = inject(MatSnackBar);

  people: Person[] = [];
  loading = true;
  working = false;
  inviteEmail = '';
  inviteRole: AppRole = 'reviewer';
  myEmail = '';

  ngOnInit(): void {
    this.peopleService.myRole().subscribe(role => this.myEmail = role.email.toLowerCase());
    this.load();
  }

  private load(): void {
    this.loading = true;
    this.peopleService.listPeople().subscribe({
      next: people => {
        this.people = people;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.snackBar.open('Could not load the people in this organization', 'Close', { duration: 4000 });
      }
    });
  }

  isMe(person: Person): boolean {
    return person.email.toLowerCase() === this.myEmail;
  }

  initialsOf(email: string): string {
    const parts = email.split('@')[0].split(/[._-]+/).filter(Boolean);
    return ((parts[0]?.[0] || '?') + (parts[1]?.[0] || '')).toUpperCase();
  }

  setRole(person: Person, role: AppRole): void {
    if (role === person.role || this.working) return;
    this.working = true;
    this.peopleService.setRole(person.email, role).subscribe({
      next: updated => {
        this.working = false;
        this.people = this.people.map(p => p.email === person.email ? { ...p, ...updated } : p);
        this.snackBar.open(
          role === 'author' ? `${person.email} can now write release notes` : `${person.email} can now only review`,
          'Close', { duration: 3000 });
      },
      error: error => {
        this.working = false;
        this.snackBar.open(error.error?.detail || 'Could not change that role', 'Close', { duration: 5000 });
      }
    });
  }

  /**
   * Two calls on purpose: the app role is ours and the invitation is hop-core's. The role
   * is recorded first so it is already waiting if the person accepts immediately.
   */
  invite(): void {
    const email = this.inviteEmail.trim();
    if (!email || this.working) return;
    this.working = true;
    this.peopleService.setRole(email, this.inviteRole).subscribe({
      next: () => {
        this.organizationService.createInvitation({ email, role: 'member' }).subscribe({
          next: () => {
            this.working = false;
            this.inviteEmail = '';
            this.snackBar.open(`Invitation sent to ${email}`, 'Close', { duration: 3000 });
            this.load();
          },
          error: error => {
            this.working = false;
            // The role is saved either way, so say what did and did not happen.
            this.snackBar.open(
              error.error?.detail || 'Role saved, but the invitation could not be sent',
              'Close', { duration: 6000 });
            this.load();
          }
        });
      },
      error: error => {
        this.working = false;
        this.snackBar.open(error.error?.detail || 'Could not save that role', 'Close', { duration: 5000 });
      }
    });
  }
}
