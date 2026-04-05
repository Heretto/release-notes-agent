import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-sso-callback',
  standalone: true,
  imports: [CommonModule, MatProgressSpinnerModule],
  template: `
    <div class="sso-callback-container">
      <mat-spinner diameter="40"></mat-spinner>
      <p>Completing sign in...</p>
    </div>
  `,
  styles: [`
    .sso-callback-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      gap: 16px;
      color: rgba(0, 0, 0, 0.54);
    }
  `]
})
export class SSOCallbackComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private authService = inject(AuthService);

  ngOnInit(): void {
    const returnUrl = this.route.snapshot.queryParams['return_url'];

    // The backend already set HttpOnly auth cookies during the redirect.
    // Verify the session is valid by refreshing, which also sets the auth state.
    this.authService.refreshToken().subscribe({
      next: () => {
        this.authService.navigateToDashboard(returnUrl);
      },
      error: () => {
        // If refresh fails, cookies weren't set properly — go back to login
        this.authService.navigateToDashboard('/login?sso_error=session_failed');
      }
    });
  }
}
