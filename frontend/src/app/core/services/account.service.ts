import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AccountInfo {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  organization_role?: string;
  organization_id?: string;
  organization_name?: string;
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
  
  private accountInfoSubject = new BehaviorSubject<AccountInfo | null>(null);
  public accountInfo$ = this.accountInfoSubject.asObservable();
  
  private isAdminSubject = new BehaviorSubject<boolean>(false);
  public isAdmin$ = this.isAdminSubject.asObservable();

  getAccountInfo(): Observable<AccountInfo> {
    return this.http.get<AccountInfo>(`${this.apiUrl}/me`).pipe(
      tap(info => {
        this.accountInfoSubject.next(info);
        this.isAdminSubject.next(info.organization_role === 'admin');
        
        // Store email for other components
        if (info.email) {
          localStorage.setItem('user_email', info.email);
        }
      })
    );
  }

  updateAccount(data: AccountUpdate): Observable<UpdateResponse> {
    return this.http.put<UpdateResponse>(`${this.apiUrl}/me`, data);
  }

  deleteAccount(confirm: boolean = false): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiUrl}/me`, {
      params: { confirm: confirm.toString() }
    });
  }
  
  clearAccountInfo(): void {
    this.accountInfoSubject.next(null);
    this.isAdminSubject.next(false);
    localStorage.removeItem('user_email');
  }
  
  isAdmin(): boolean {
    const currentInfo = this.accountInfoSubject.value;
    return currentInfo?.organization_role === 'admin' || false;
  }
}