import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface JiraCredential {
  id?: string;
  name: string;
  server_url: string;
  email: string;
  api_token: string;
}

export interface HerettoCredential {
  id?: string;
  name: string;
  api_key: string;
  organization_id: string;
  environment: string;
}

export interface AICredential {
  id?: string;
  type?: 'AI';
  name: string;
  provider: string;
  api_key: string;
  model?: string;
  base_url?: string;
  organization_id?: string;
  created_at?: string;
  updated_at?: string;
}

@Injectable({
  providedIn: 'root'
})
export class CredentialsService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/credentials`;

  // Jira credentials
  getJiraCredentials(): Observable<JiraCredential[]> {
    return this.http.get<JiraCredential[]>(`${this.apiUrl}/jira`);
  }

  createJiraCredential(credential: JiraCredential): Observable<JiraCredential> {
    return this.http.post<JiraCredential>(`${this.apiUrl}/jira`, credential);
  }

  updateJiraCredential(id: string, credential: JiraCredential): Observable<JiraCredential> {
    return this.http.put<JiraCredential>(`${this.apiUrl}/jira/${id}`, credential);
  }

  deleteJiraCredential(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/jira/${id}`);
  }

  // Heretto credentials
  getHerettoCredentials(): Observable<HerettoCredential[]> {
    return this.http.get<HerettoCredential[]>(`${this.apiUrl}/heretto`);
  }

  createHerettoCredential(credential: HerettoCredential): Observable<HerettoCredential> {
    return this.http.post<HerettoCredential>(`${this.apiUrl}/heretto`, credential);
  }

  updateHerettoCredential(id: string, credential: HerettoCredential): Observable<HerettoCredential> {
    return this.http.put<HerettoCredential>(`${this.apiUrl}/heretto/${id}`, credential);
  }

  deleteHerettoCredential(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/heretto/${id}`);
  }

  // AI credentials
  getAICredentials(): Observable<AICredential[]> {
    return this.http.get<AICredential[]>(`${this.apiUrl}/ai`);
  }

  getAICredential(id: string): Observable<AICredential> {
    return this.http.get<AICredential>(`${this.apiUrl}/ai/${id}`);
  }

  createAICredential(credential: AICredential): Observable<AICredential> {
    return this.http.post<AICredential>(`${this.apiUrl}/ai`, credential);
  }

  updateAICredential(id: string, credential: any): Observable<AICredential> {
    // Transform to backend format
    const updateData: any = {
      name: credential.name
    };
    
    // Only include credentials if we have actual updates
    const credentials: any = {};
    if (credential.api_key) {
      credentials.api_key = credential.api_key;
    }
    if (credential.model !== undefined) {
      credentials.model = credential.model || '';
    }
    
    // Only include credentials object if it has properties
    if (Object.keys(credentials).length > 0) {
      updateData.credentials = credentials;
    }
    
    return this.http.put<AICredential>(`${this.apiUrl}/${id}`, updateData);
  }

  deleteAICredential(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  // Test credential connection
  testCredential(id: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/${id}/test`, {});
  }
}