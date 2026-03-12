import { inject } from '@angular/core';
import { Router, CanActivateFn } from '@angular/router';
import { AuthService } from './auth.service';

/** Only allow relative paths starting with '/' — reject anything that looks external. */
function isSafeReturnUrl(url: string): boolean {
  return url.startsWith('/') && !url.startsWith('//') && !url.includes('://');
}

export const AuthGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return true;
  }

  const returnUrl = isSafeReturnUrl(state.url) ? state.url : '/dashboard';
  router.navigate(['/login'], { queryParams: { returnUrl } });
  return false;
};