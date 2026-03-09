import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';
import { tap, shareReplay } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export interface Organization {
  id: string;
  name: string;
  slug: string;
  settings?: any;
  created_at: string;
  updated_at?: string;
  member_count?: number;
}

export interface OrganizationMember {
  id: string;
  user_id: string;
  user_email: string;
  role: 'admin' | 'member';
  joined_at: string;
  invited_by?: string;
}

export interface OrganizationInvitation {
  id: string;
  organization_id: string;
  organization_name: string;
  email: string;
  role: 'admin' | 'member';
  token: string;
  invited_by_email: string;
  expires_at: string;
  created_at: string;
}

@Injectable({
  providedIn: 'root'
})
export class OrganizationService {
  private http = inject(HttpClient);
  
  private currentOrganizationSubject = new BehaviorSubject<Organization | null>(null);
  public currentOrganization$ = this.currentOrganizationSubject.asObservable();
  
  private organizationsCache$?: Observable<Organization[]>;
  
  getCurrentOrganization(): Observable<Organization> {
    return this.http.get<Organization>(`${environment.apiUrl}/organizations/current`).pipe(
      tap(org => this.currentOrganizationSubject.next(org)),
      shareReplay(1)
    );
  }
  
  listUserOrganizations(): Observable<Organization[]> {
    if (!this.organizationsCache$) {
      this.organizationsCache$ = this.http.get<Organization[]>(`${environment.apiUrl}/organizations`).pipe(
        shareReplay(1)
      );
    }
    return this.organizationsCache$;
  }
  
  createOrganization(data: { name: string }): Observable<Organization> {
    return this.http.post<Organization>(`${environment.apiUrl}/organizations`, data).pipe(
      tap(() => this.clearCache())
    );
  }
  
  updateOrganization(data: { name?: string; settings?: any }): Observable<Organization> {
    return this.http.patch<Organization>(`${environment.apiUrl}/organizations/current`, data).pipe(
      tap(org => this.currentOrganizationSubject.next(org))
    );
  }
  
  // Member management
  listMembers(): Observable<OrganizationMember[]> {
    return this.http.get<OrganizationMember[]>(`${environment.apiUrl}/organizations/current/members`);
  }
  
  updateMemberRole(memberId: string, role: 'admin' | 'member'): Observable<OrganizationMember> {
    return this.http.patch<OrganizationMember>(
      `${environment.apiUrl}/organizations/members/${memberId}`, 
      { role }
    );
  }
  
  removeMember(memberId: string): Observable<any> {
    return this.http.delete(`${environment.apiUrl}/organizations/members/${memberId}`);
  }
  
  // Invitation management
  createInvitation(data: { email: string; role: 'admin' | 'member' }): Observable<OrganizationInvitation> {
    return this.http.post<OrganizationInvitation>(
      `${environment.apiUrl}/organizations/invitations`, 
      data
    );
  }
  
  listInvitations(): Observable<OrganizationInvitation[]> {
    return this.http.get<OrganizationInvitation[]>(`${environment.apiUrl}/organizations/invitations`);
  }
  
  cancelInvitation(invitationId: string): Observable<any> {
    return this.http.delete(`${environment.apiUrl}/organizations/invitations/${invitationId}`);
  }
  
  acceptInvitation(token: string): Observable<any> {
    return this.http.post(`${environment.apiUrl}/organizations/invitations/accept/${token}`, {});
  }
  
  switchOrganization(orgId: string) {
    return this.http.post<{ access_token: string; refresh_token: string; token_type: string }>(
      `${environment.apiUrl}/organizations/switch/${orgId}`, {}
    ).pipe(
      tap(() => {
        this.clearCache();
        this.currentOrganizationSubject.next(null);
      })
    );
  }

  private clearCache(): void {
    this.organizationsCache$ = undefined;
  }
}