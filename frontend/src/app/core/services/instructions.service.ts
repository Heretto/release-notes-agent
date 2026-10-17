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
  /** 'jql' — jql_query is a template — or 'releases' — one query per Jira fix version. */
  source_mode?: 'jql' | 'releases';
  jira_project?: string | null;
  extra_jql?: string | null;
  jira_credential_id?: string | null;
  writer_agent_id?: string | null;
  analysis_agent_id?: string | null;
  writer_agent_name?: string | null;
  analysis_agent_name?: string | null;
  product_name?: string | null;
  relevance_guidance?: string | null;
  organization_guidance?: string | null;
  chunking_strategy: ChunkingStrategy;
  /** How topics are laid out; absent means the default shape. */
  layout?: TopicLayout;
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
  /**
   * One page of the Jira releases this instruction set can run on, newest first.
   * Paginated because a long-lived project has hundreds of versions and the picker shows
   * a handful; `next_start` continues where the last page stopped.
   */
  listReleases(instructionId: string, startAt = 0, maxResults = 5): Observable<JiraReleaseList> {
    return this.http.get<JiraReleaseList>(`${this.apiUrl}/${instructionId}/releases`, {
      params: { start_at: startAt, max_results: maxResults }
    });
  }

  testQuery(instructionId: string, credentialId: string, variables: Record<string, string> = {}): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/${instructionId}/test`, {
      credential_id: credentialId,
      variables
    });
  }
}

/** One Jira release (fix version) an instruction set in "releases" mode can run on. */
/** How an instruction set lays its topics out. Only the structured mode exists so far. */
export interface StructuredLayout {
  group_heading: 'section' | 'paragraph' | 'none';
  notes_wrapper: 'none' | 'ul' | 'ol';
  note_element: 'div' | 'li';
  shortdesc: 'omit' | 'empty' | 'text';
  shortdesc_text: string;
}

export type LayoutMode = 'structured' | 'template' | 'agent';

export interface TopicLayout {
  mode: LayoutMode;
  structured: StructuredLayout;
  /** A DITA topic with rn-group / rn-notes markers. */
  template: { dita: string };
  /** The structure described in words; an agent turns it into a template per release. */
  agent: { guidance: string };
}

/** Offered when someone switches to template mode with nothing written yet. */
export const STARTER_TEMPLATE = `<topic id="release-notes">
  <title>{title}</title>
  <shortdesc/>
  <body>
    <section outputclass="rn-group">
      <p><b>{group}</b></p>
      <ul outputclass="rn-notes"/>
    </section>
  </body>
</topic>`;

export const DEFAULT_LAYOUT: StructuredLayout = {
  group_heading: 'section',
  notes_wrapper: 'none',
  note_element: 'div',
  shortdesc: 'omit',
  shortdesc_text: ''
};

export interface JiraRelease {
  id: string;
  name: string;
  description: string;
  released: boolean;
  archived: boolean;
  /** Release date once released, otherwise the planned start date; '' when Jira has none. */
  date: string;
  issue_count: number;
}

export interface JiraReleaseList {
  project: string;
  releases: JiraRelease[];
  /** How many the project has in total, so the picker can say "5 of 23". */
  total: number;
  has_more: boolean;
  next_start: number;
}
