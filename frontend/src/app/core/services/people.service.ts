import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, shareReplay, tap } from 'rxjs';
import { environment } from '../../../environments/environment';

/** What the app lets someone do, beside hop-core's organization role. */
export type AppRole = 'author' | 'reviewer';

export interface MyRole {
  email: string;
  role: AppRole;
  is_author: boolean;
  is_org_admin: boolean;
}

export interface Person {
  email: string;
  role: AppRole;
  user_id?: string | null;
  org_role?: string | null;
  /** The role is set for an address with no account behind it yet. */
  invited: boolean;
}

@Injectable({ providedIn: 'root' })
export class PeopleService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/people`;

  /**
   * Cached: the guard asks on every navigation and the answer only changes when an admin
   * changes it, which is a different session. `clear()` drops it after a sign-out.
   */
  private myRole$?: Observable<MyRole>;
  private cached: MyRole | null = null;

  myRole(): Observable<MyRole> {
    if (!this.myRole$) {
      this.myRole$ = this.http.get<MyRole>(`${this.apiUrl}/me`).pipe(
        tap(role => this.cached = role),
        shareReplay(1)
      );
    }
    return this.myRole$;
  }

  /** The last answer, for templates that cannot wait for a request. */
  get current(): MyRole | null {
    return this.cached;
  }

  clear(): void {
    this.myRole$ = undefined;
    this.cached = null;
  }

  listPeople(): Observable<Person[]> {
    return this.http.get<Person[]>(this.apiUrl);
  }

  /** Accepts an address with no account yet — the role waits for the invitation. */
  setRole(email: string, role: AppRole): Observable<Person> {
    return this.http.patch<Person>(`${this.apiUrl}/role`, { email, role }).pipe(
      tap(() => {
        // Changing your own role is refused by the API, but someone else's change can
        // still invalidate a cached answer in a long-lived tab.
        if (this.cached?.email?.toLowerCase() === email.trim().toLowerCase()) this.clear();
      })
    );
  }
}

/** Convenience for guards that only need yes/no and can fall back safely. */
export function isAuthorOf(role: MyRole | null): boolean {
  return !!role?.is_author;
}

export const NO_ROLE: Observable<MyRole | null> = of(null);
