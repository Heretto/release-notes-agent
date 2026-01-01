import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AccountInfo {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface AccountUpdate {
  email?: string;
  current_password?: string;
  new_password?: string;
}

export interface UpdateResponse {
  message: string;
  email: string;
}

@Injectable({
  providedIn: 'root'
})
export class AccountService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/account`;

  getAccountInfo(): Observable<AccountInfo> {
    return this.http.get<AccountInfo>(`${this.apiUrl}/me`);
  }

  updateAccount(data: AccountUpdate): Observable<UpdateResponse> {
    return this.http.put<UpdateResponse>(`${this.apiUrl}/me`, data);
  }

  deleteAccount(confirm: boolean = false): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/me`, {
      params: { confirm: confirm.toString() }
    });
  }
}