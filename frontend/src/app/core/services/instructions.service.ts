import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface InstructionSet {
  id?: string;
  name: string;
  description?: string;
  jql_query: string;
  system_prompt: string;
  user_instructions?: string;
  dita_template_id?: string;
  heretto_folder_id?: string;
  publish_to_heretto: boolean;
  is_default: boolean;
  created_at?: string;
  updated_at?: string;
}

@Injectable({
  providedIn: 'root'
})
export class InstructionsService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/instructions`;

  getInstructionSets(): Observable<InstructionSet[]> {
    return this.http.get<InstructionSet[]>(`${this.apiUrl}`);
  }

  getInstructionSet(id: string): Observable<InstructionSet> {
    return this.http.get<InstructionSet>(`${this.apiUrl}/${id}`);
  }

  createInstructionSet(instruction: InstructionSet): Observable<InstructionSet> {
    return this.http.post<InstructionSet>(`${this.apiUrl}`, instruction);
  }

  updateInstructionSet(id: string, instruction: Partial<InstructionSet>): Observable<InstructionSet> {
    return this.http.put<InstructionSet>(`${this.apiUrl}/${id}`, instruction);
  }

  deleteInstructionSet(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  setAsDefault(id: string): Observable<InstructionSet> {
    return this.updateInstructionSet(id, { is_default: true });
  }

  testQuery(instructionId: string, credentialId: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/${instructionId}/test`, {
      credential_id: credentialId
    });
  }
}