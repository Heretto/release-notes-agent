import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface UserOrganizationInfo {
  id: string;
  name: string;
  slug: string;
  role: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at?: number;
  organizations?: UserOrganizationInfo[];
}

interface User {
  id: string;
  email: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);

  private currentUserSubject = new BehaviorSubject<User | null>(null);
  public currentUser$ = this.currentUserSubject.asObservable();

  /** In-memory auth state — not accessible to XSS via storage APIs. */
  private loggedIn = false;
  private expiresAt: number | null = null;

  constructor() {
    // Restore session flag on page reload (sessionStorage is tab-scoped
    // and cleared when the tab closes, unlike localStorage).
    if (sessionStorage.getItem('auth_active') === '1') {
      this.loggedIn = true;
      const exp = sessionStorage.getItem('auth_exp');
      this.expiresAt = exp ? Number(exp) : null;
    }
  }

  private setAuthState(expiresAt?: number): void {
    this.loggedIn = true;
    this.expiresAt = expiresAt ?? null;
    sessionStorage.setItem('auth_active', '1');
    if (expiresAt) {
      sessionStorage.setItem('auth_exp', String(expiresAt));
    }
  }

  private clearAuthState(): void {
    this.loggedIn = false;
    this.expiresAt = null;
    sessionStorage.removeItem('auth_active');
    sessionStorage.removeItem('auth_exp');
  }

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${environment.apiUrl}/auth/login`, {
      email,
      password
    }).pipe(
      tap((res) => {
        this.setAuthState(res.expires_at);
      })
    );
  }

  navigateToDashboard(returnUrl?: string): void {
    if (returnUrl) {
      try {
        const decoded = decodeURIComponent(returnUrl);
        if (decoded.startsWith('/') && !decoded.startsWith('//') && !decoded.includes('://')) {
          this.router.navigateByUrl(returnUrl);
          return;
        }
      } catch {
        // Malformed URL — fall through to default
      }
    }
    this.router.navigate(['/dashboard']);
  }

  /** Called after org switch — cookies are set by the backend, just keep flag + expiry. */
  updateTokens(response: { access_token: string; refresh_token: string; expires_at?: number }): void {
    this.setAuthState(response.expires_at);
  }

  register(email: string, password: string, organizationName?: string): Observable<any> {
    const payload: any = {
      email,
      password
    };

    if (organizationName) {
      payload.organization_name = organizationName;
    }

    return this.http.post(`${environment.apiUrl}/auth/register`, payload);
  }

  logout(): void {
    // Tell the backend to clear cookies
    this.http.post(`${environment.apiUrl}/auth/logout`, {}).subscribe({
      error: () => {} // best-effort
    });
    this.clearAuthState();
    this.currentUserSubject.next(null);
    this.router.navigate(['/login']);
  }

  refreshToken(): Observable<LoginResponse> {
    // Refresh token is sent automatically via HttpOnly cookie
    return this.http.post<LoginResponse>(`${environment.apiUrl}/auth/refresh`, {}).pipe(
      tap((res) => {
        this.setAuthState(res.expires_at);
      })
    );
  }

  isAuthenticated(): boolean {
    if (!this.loggedIn) {
      return false;
    }
    if (this.expiresAt !== null && Date.now() / 1000 >= this.expiresAt) {
      this.clearAuthState();
      return false;
    }
    return true;
  }

  getSSOProviders(): Observable<{google: boolean, microsoft: boolean}> {
    return this.http.get<{google: boolean, microsoft: boolean}>(`${environment.apiUrl}/auth/sso/providers`);
  }
}
