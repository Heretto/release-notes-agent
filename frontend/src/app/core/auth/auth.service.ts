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

  private readonly LOGGED_IN_KEY = 'logged_in';
  private readonly EXPIRES_AT_KEY = 'token_expires_at';

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${environment.apiUrl}/auth/login`, {
      email,
      password
    }).pipe(
      tap((res) => {
        localStorage.setItem(this.LOGGED_IN_KEY, 'true');
        localStorage.setItem('user_email', email);
        if (res.expires_at) {
          localStorage.setItem(this.EXPIRES_AT_KEY, String(res.expires_at));
        }
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
    localStorage.setItem(this.LOGGED_IN_KEY, 'true');
    if (response.expires_at) {
      localStorage.setItem(this.EXPIRES_AT_KEY, String(response.expires_at));
    }
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
    localStorage.removeItem(this.LOGGED_IN_KEY);
    localStorage.removeItem(this.EXPIRES_AT_KEY);
    localStorage.removeItem('user_email');
    this.currentUserSubject.next(null);
    this.router.navigate(['/login']);
  }

  refreshToken(): Observable<LoginResponse> {
    // Refresh token is sent automatically via HttpOnly cookie
    return this.http.post<LoginResponse>(`${environment.apiUrl}/auth/refresh`, {}).pipe(
      tap((res) => {
        localStorage.setItem(this.LOGGED_IN_KEY, 'true');
        if (res.expires_at) {
          localStorage.setItem(this.EXPIRES_AT_KEY, String(res.expires_at));
        }
      })
    );
  }

  isAuthenticated(): boolean {
    if (localStorage.getItem(this.LOGGED_IN_KEY) !== 'true') {
      return false;
    }
    const expiresAt = localStorage.getItem(this.EXPIRES_AT_KEY);
    if (expiresAt) {
      // Token expired — clear state and deny access
      if (Date.now() / 1000 >= Number(expiresAt)) {
        localStorage.removeItem(this.LOGGED_IN_KEY);
        localStorage.removeItem(this.EXPIRES_AT_KEY);
        return false;
      }
    }
    return true;
  }
}
