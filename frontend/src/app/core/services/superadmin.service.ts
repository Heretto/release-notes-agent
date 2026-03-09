import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface SuperadminOrgListItem {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  member_count: number;
  created_by_email: string | null;
  last_activity: string | null;
}

export interface SuperadminOrgMember {
  id: string;
  user_id: string;
  email: string;
  role: string;
  is_active: boolean;
  joined_at: string | null;
}

export interface SuperadminOrgDetail {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
  member_count: number;
  job_count: number;
  created_by_email: string | null;
  last_activity: string | null;
  members: SuperadminOrgMember[];
}

export interface SuperadminInvitation {
  id: string;
  email: string;
  role: string;
  token: string;
  expires_at: string;
}

@Injectable({
  providedIn: 'root'
})
export class SuperadminService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/superadmin`;

  listOrganizations(): Observable<SuperadminOrgListItem[]> {
    return this.http.get<SuperadminOrgListItem[]>(`${this.apiUrl}/organizations`);
  }

  getOrganization(orgId: string): Observable<SuperadminOrgDetail> {
    return this.http.get<SuperadminOrgDetail>(`${this.apiUrl}/organizations/${orgId}`);
  }

  deleteOrganization(orgId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/organizations/${orgId}`);
  }

  addMember(orgId: string, email: string, role: string): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}/organizations/${orgId}/members`, { email, role });
  }

  removeMember(orgId: string, userId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/organizations/${orgId}/members/${userId}`);
  }

  inviteUser(orgId: string, email: string, role: string): Observable<SuperadminInvitation> {
    return this.http.post<SuperadminInvitation>(`${this.apiUrl}/organizations/${orgId}/invitations`, { email, role });
  }
}
