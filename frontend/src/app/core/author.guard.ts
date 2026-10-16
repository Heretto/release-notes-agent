import { inject } from '@angular/core';
import { CanActivateFn, Router, UrlTree } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { PeopleService } from './services/people.service';

/**
 * Keeps reviewers out of the authoring app.
 *
 * Guards the shell, not individual pages: a reviewer has no business anywhere inside it,
 * and guarding the one parent means a page added later is covered without anyone
 * remembering to. The review view sits outside the shell, so someone who followed a review
 * link lands there and is never sent here — which is what makes "if they did not come
 * through a review URL, explain how to get access" fall out of the routing rather than
 * needing to be detected.
 *
 * The API enforces the same rule independently (app/api/reviewer_access.py); this only
 * decides what the browser shows.
 */
export const authorGuard: CanActivateFn = (): any => {
  const people = inject(PeopleService);
  const router = inject(Router);

  return people.myRole().pipe(
    map(role => role.is_author ? true : router.createUrlTree(['/review-access'])),
    // A failed lookup must not strand someone on a blank page. The API is the real gate,
    // so letting the navigation through costs nothing: a reviewer still gets 403s.
    catchError(() => of(true as boolean | UrlTree))
  );
};

/** For the People page, which is for organization admins only. */
export const orgAdminGuard: CanActivateFn = (): any => {
  const people = inject(PeopleService);
  const router = inject(Router);

  return people.myRole().pipe(
    map(role => role.is_org_admin ? true : router.createUrlTree(['/dashboard'])),
    catchError(() => of(router.createUrlTree(['/dashboard']) as boolean | UrlTree))
  );
};
