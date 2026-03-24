import { inject } from '@angular/core';
import { Router, CanActivateFn } from '@angular/router';
import { AccountService } from '../services/account.service';
import { map, take, switchMap, of } from 'rxjs';

export const AdminGuard: CanActivateFn = (route, state) => {
  const accountService = inject(AccountService);
  const router = inject(Router);

  return accountService.accountInfo$.pipe(
    take(1),
    switchMap(info => {
      if (info) {
        return of(info);
      }
      return accountService.getAccountInfo();
    }),
    map(info => {
      if (info?.organization_role === 'admin' || info?.is_superuser) {
        return true;
      }
      router.navigate(['/dashboard']);
      return false;
    })
  );
};
