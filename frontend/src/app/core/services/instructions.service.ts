import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { JqlVariableSpec } from '../jql-variables';
import { ChunkingStrategy } from './jobs.service';

export interface InstructionSet {
  id?: string;
  name: string;
  description?: string;
  /** A JQL template: {name} tokens are filled in when a release is started. */
  jql_query: string;
  /** Keyed by the {name} tokens in jql_query; the server keeps the two in step. */
  variables?: Record<string, JqlVariableSpec>;
  jira_credential_id?: string | null;
  writer_agent_id?: string | null;
  analysis_agent_id?: string | null;
  writer_agent_name?: string | null;
  analysis_agent_name?: string | null;
  product_name?: string | null;
  relevance_guidance?: string | null;
  organization_guidance?: string | null;
  chunking_strategy: ChunkingStrategy;
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

  /** `variables` fill the query's `{name}` tokens; the server does the substituting. */
  testQuery(instructionId: string, credentialId: string, variables: Record<string, string> = {}): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/${instructionId}/test`, {
      credential_id: credentialId,
      variables
    });
  }
}
