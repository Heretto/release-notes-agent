import { Component, OnInit, inject, ChangeDetectionStrategy } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HopAuthService } from '@heretto/hop-ui';
import { PeopleService } from '../../core/services/people.service';

/**
 * Where a reviewer lands if they open the app rather than a review link.
 *
 * Their account works — it just cannot author release notes yet. This says so plainly and
 * tells them the one thing that fixes it, rather than showing an empty app or a 403.
 */
@Component({
  selector: 'app-promotion-required',
  standalone: true,
  imports: [MatButtonModule, MatIconModule],
  template: `
    <div class="page">
      <div class="card">
        <mat-icon class="mark">rate_review</mat-icon>
        <h1>You have reviewer access</h1>
        <p class="lead">
          Your account can read release notes and comment on them. Writing and running
          releases needs author access, which an administrator of your organization can
          grant.
        </p>

        <div class="what">
          <span class="what-label">Ask an administrator to make this account an author</span>
          <code>{{ email }}</code>
        </div>

        <p class="muted">
          Already reviewing something? Open the review link you were sent — reviewing works
          with the access you have.
        </p>

        <div class="actions">
          <button mat-stroked-button (click)="copyEmail()">
            <mat-icon>content_copy</mat-icon> Copy my address
          </button>
          <button mat-stroked-button (click)="signOut()">Sign out</button>
        </div>
      </div>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    .page { display: flex; align-items: center; justify-content: center; min-height: 100vh;
      padding: 24px; background: var(--bg-secondary); }
    .card { max-width: 520px; width: 100%; background: var(--bg-primary); border: 1px solid var(--border-default);
      border-radius: 12px; padding: 32px; text-align: center; }
    .mark { font-size: 40px; width: 40px; height: 40px; color: var(--color-primary); }
    h1 { margin: 12px 0 8px; font-size: 22px; }
    .lead { margin: 0 0 20px; font-size: 14px; line-height: 1.6; color: var(--text-secondary); }
    .what { border: 1px solid var(--border-default); border-radius: 8px; padding: 14px 16px;
      background: var(--bg-secondary); margin-bottom: 16px; }
    .what-label { display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; }
    .what code { font-family: var(--font-mono); font-size: 14px; word-break: break-all; }
    .muted { font-size: 13px; color: var(--text-tertiary); margin: 0 0 20px; line-height: 1.5; }
    .actions { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
  `]
})
export class PromotionRequiredComponent implements OnInit {
  private people = inject(PeopleService);
  private auth = inject(HopAuthService);
  private snackBar = inject(MatSnackBar);

  email = '';

  ngOnInit(): void {
    this.people.myRole().subscribe({
      next: role => {
        this.email = role.email;
        // An author who reaches this page by typing the URL should not sit on it.
        if (role.is_author) window.location.href = '/dashboard';
      },
      error: () => this.email = ''
    });
  }

  copyEmail(): void {
    navigator.clipboard?.writeText(this.email).then(
      () => this.snackBar.open('Address copied', 'Close', { duration: 2000 }),
      () => this.snackBar.open('Could not copy — select the address and copy it', 'Close', { duration: 4000 })
    );
  }

  signOut(): void {
    this.people.clear();
    this.auth.logout();
  }
}
