import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from './auth.service';
import { catchError, switchMap, throwError } from 'rxjs';

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);

  // Attach cookies on every request to our API
  const csrfToken = getCookie('csrf_token');
  const headers: Record<string, string> = {};
  if (csrfToken && !['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
    headers['X-CSRF-Token'] = csrfToken;
  }
  req = req.clone({ withCredentials: true, setHeaders: headers });

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !req.url.includes('/auth/refresh') && !req.url.includes('/auth/login')) {
        // Try to refresh token (cookie is sent automatically)
        return authService.refreshToken().pipe(
          switchMap(() => {
            // Retry original request — new cookie is already set
            return next(req.clone({ withCredentials: true }));
          }),
          catchError(refreshError => {
            // Refresh failed, logout user
            authService.logout();
            return throwError(() => refreshError);
          })
        );
      }
      return throwError(() => error);
    })
  );
};
