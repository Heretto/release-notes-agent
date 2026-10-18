import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type JobStage =
  | 'fetch_issues' | 'evaluate' | 'consolidate' | 'organize' | 'write' | 'assemble' | 'publish' | 'done';
export type ItemStatus = 'draft' | 'review' | 'approved' | 'rejected';
export type ChunkingStrategy = 'single' | 'by_group' | 'by_component';

export const JOB_STAGES: { key: JobStage; label: string }[] = [
  { key: 'fetch_issues', label: 'Fetch issues' },
  { key: 'evaluate', label: 'Evaluate' },
  { key: 'consolidate', label: 'Consolidate' },
  { key: 'organize', label: 'Organize' },
  { key: 'write', label: 'Write' },
  { key: 'assemble', label: 'Assemble' },
  { key: 'publish', label: 'Publish' },
];

export const CHUNKING_STRATEGIES: { value: ChunkingStrategy; label: string; hint: string }[] = [
  { value: 'single', label: 'Single topic', hint: 'Every release note in one topic (default)' },
  { value: 'by_group', label: 'One topic per group', hint: 'A topic for each group: features, fixes, …' },
  { value: 'by_component', label: 'One topic per component', hint: 'A topic for each Jira component' },
];

export const ITEM_STATUSES: { value: ItemStatus; label: string }[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'review', label: 'In review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

export interface JobCreate {
  /** Omit to have the server resolve the instruction set's template from `variables`. */
  jql_query?: string;
  /** {name: value} for the instruction set's JQL variables. */
  variables?: Record<string, string>;
  /** The chosen Jira release, when the instruction set's source is Jira releases. */
  release?: string;
  instruction_set_id: string;
  title?: string;
  output_filename: string;
  publish_to_heretto: boolean;
  heretto_folder_id?: string;
  max_tickets?: number;
  chunking_strategy?: ChunkingStrategy;
}

export interface JobUpdate {
  title?: string | null;
  output_filename?: string;
  max_tickets?: number | null;
  chunking_strategy?: ChunkingStrategy;
  publish_to_heretto?: boolean;
  heretto_folder_id?: string | null;
  /** New values for the instruction set's JQL variables — the server re-resolves. */
  variables?: Record<string, string>;
  /** The chosen Jira release, for a set whose source is Jira releases. */
  release?: string;
}

export interface JobCounts {
  issues: number;
  relevant_issues: number;
  items: number;
  approved_items: number;
  attention_items: number;
  topics: number;
}

export interface Job {
  id: string;
  /** The variable values this run resolved its query from. */
  variables?: Record<string, string>;
  user_id: string;
  instruction_set_id?: string;
  /** Named on the response so details can show it without a second request. */
  instruction_set_name?: string | null;
  title?: string | null;
  jql_query: string;
  /** False when the query was supplied directly, which stops a rerun rebuilding it. */
  uses_instruction_query?: boolean;
  /** This release's own publish settings, which override the instruction set's. */
  auto_publish?: boolean;
  heretto_folder_id?: string | null;
  status: JobStatus;
  triggered_by: 'manual' | 'webhook' | 'scheduled';
  output_filename?: string;
  tickets_processed: number;
  max_tickets?: number;
  error_message?: string | null;
  stage?: JobStage | null;
  stage_message?: string | null;
  chunking_strategy: ChunkingStrategy;
  run_count: number;
  last_run_at?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  counts?: JobCounts;
}

export interface JobIssue {
  id: string;
  issue_key: string;
  url?: string | null;
  summary: string;
  description?: string | null;
  issue_type?: string | null;
  status?: string | null;
  priority?: string | null;
  labels: string[];
  components: string[];
  fix_versions: string[];
  comments: string[];
  assignee?: string | null;
  reporter?: string | null;
  jira_created?: string | null;
  jira_updated?: string | null;
  relevance: 'pending' | 'relevant' | 'not_relevant';
  relevance_reason?: string | null;
  in_query: boolean;
  item_ids: string[];
  changed_at?: string | null;
}

export interface ItemHistoryEntry {
  id: string;
  event_type: string;
  actor: 'system' | 'agent' | 'user';
  user_id?: string | null;
  summary: string;
  details?: Record<string, any> | null;
  created_at?: string | null;
}

export interface ReleaseNoteItem {
  id: string;
  job_id: string;
  topic_id?: string | null;
  fragment_id: string;
  position: number;
  group_name?: string | null;
  title: string;
  summary: string;
  dita_content: string;
  status: ItemStatus;
  needs_attention: boolean;
  attention_reason?: string | null;
  user_edited: boolean;
  issue_keys: string[];
  has_notes: boolean;
  /** Review is its own axis, separate from `status`: who was asked, and their answer. */
  reviewer_id?: string | null;
  reviewer_email?: string | null;
  reviewed: boolean;
  comment_count: number;
  /** Who put the note into `approved`, and when. Cleared if it leaves that status. */
  approved_by_email?: string | null;
  approved_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ItemComment {
  id: string;
  user_id?: string | null;
  user_email?: string | null;
  body: string;
  /** Dealt with, not deleted — a resolved comment stays readable alongside the change. */
  resolved: boolean;
  resolved_at?: string | null;
  resolved_by_email?: string | null;
  created_at?: string | null;
}

export interface ReleaseNoteItemDetail extends ReleaseNoteItem {
  issues: JobIssue[];
  notes: string;
  history: ItemHistoryEntry[];
  comments: ItemComment[];
}

export interface ReleaseNoteItemUpdate {
  title?: string;
  summary?: string;
  dita_content?: string;
  status?: ItemStatus;
  group_name?: string;
  notes?: string;
  clear_attention?: boolean;
  /** `null` unassigns — the field is only sent when it is meant to change. */
  reviewer_id?: string | null;
  reviewed?: boolean;
}

export interface ReleaseNoteTopic {
  id: string;
  position: number;
  slug: string;
  title: string;
  filename: string;
  dita_content: string;
  html?: string | null;
  render_warnings: string[];
  heretto_doc_id?: string | null;
  published_at?: string | null;
  item_ids: string[];
  updated_at?: string | null;
}

export interface ChatAction {
  tool: string;
  args: Record<string, any>;
  ok: boolean;
  result: string;
  description?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  actions?: ChatAction[] | null;
  user_id?: string | null;
  created_at?: string | null;
}

export interface ChatSendResponse {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  changed_item_ids: string[];
  topics_changed: boolean;
}

export interface JobRequestLog {
  id: string;
  type: string;
  status: 'pending' | 'success' | 'failed';
  timestamp: string;
  duration_ms?: number | null;
  error_message?: string | null;
  request_data: any;
  response_data: any;
}

export interface PublishResult {
  success: boolean;
  document_id?: string | null;
  message: string;
  /** Which topic this result is for. */
  title?: string | null;
}

/** What a publish did, and the folder to open to see it. */
export interface PublishResponse {
  folder_id?: string | null;
  folder_url?: string | null;
  results: PublishResult[];
}

@Injectable({
  providedIn: 'root'
})
export class JobsService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/jobs`;

  // ── Jobs ──────────────────────────────────────────────────────────────────

  getJobs(status?: JobStatus): Observable<Job[]> {
    const params = status ? new HttpParams().set('status_filter', status) : undefined;
    return this.http.get<Job[]>(`${this.apiUrl}`, { params });
  }

  getJob(id: string): Observable<Job> {
    return this.http.get<Job>(`${this.apiUrl}/${id}`);
  }

  createJob(job: JobCreate): Observable<Job> {
    return this.http.post<Job>(`${this.apiUrl}`, job);
  }

  cancelJob(id: string): Observable<void> {
    return this.http.post<void>(`${this.apiUrl}/${id}/cancel`, {});
  }

  /** Run the pipeline again on the same job; unchanged issues keep their notes. */
  rerunJob(id: string): Observable<Job> {
    return this.http.post<Job>(`${this.apiUrl}/${id}/rerun`, {});
  }

  retryJob(id: string): Observable<Job> {
    return this.http.post<Job>(`${this.apiUrl}/${id}/retry`, {});
  }

  deleteJob(id: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${id}`);
  }

  getJobRequests(jobId: string): Observable<JobRequestLog[]> {
    return this.http.get<JobRequestLog[]>(`${this.apiUrl}/${jobId}/requests`);
  }

  // ── Artifacts (kept for downloads) ────────────────────────────────────────

  getJobArtifacts(id: string): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/${id}/artifacts`);
  }

  getArtifactContent(jobId: string, artifactId: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/${jobId}/artifacts/${artifactId}/content`);
  }

  downloadArtifact(jobId: string, artifactId: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${jobId}/artifacts/${artifactId}/download`, { responseType: 'blob' });
  }

  // ── Workspace ─────────────────────────────────────────────────────────────

  getIssues(jobId: string): Observable<JobIssue[]> {
    return this.http.get<JobIssue[]>(`${this.apiUrl}/${jobId}/issues`);
  }

  getItems(jobId: string): Observable<ReleaseNoteItem[]> {
    return this.http.get<ReleaseNoteItem[]>(`${this.apiUrl}/${jobId}/items`);
  }

  getItem(jobId: string, itemId: string): Observable<ReleaseNoteItemDetail> {
    return this.http.get<ReleaseNoteItemDetail>(`${this.apiUrl}/${jobId}/items/${itemId}`);
  }

  updateItem(jobId: string, itemId: string, update: ReleaseNoteItemUpdate): Observable<ReleaseNoteItemDetail> {
    return this.http.patch<ReleaseNoteItemDetail>(`${this.apiUrl}/${jobId}/items/${itemId}`, update);
  }

  listComments(jobId: string, itemId: string): Observable<ItemComment[]> {
    return this.http.get<ItemComment[]>(`${this.apiUrl}/${jobId}/items/${itemId}/comments`);
  }

  addComment(jobId: string, itemId: string, body: string): Observable<ItemComment> {
    return this.http.post<ItemComment>(`${this.apiUrl}/${jobId}/items/${itemId}/comments`, { body });
  }

  resolveComment(jobId: string, itemId: string, commentId: string, resolved: boolean): Observable<ItemComment> {
    return this.http.patch<ItemComment>(
      `${this.apiUrl}/${jobId}/items/${itemId}/comments/${commentId}`, { resolved });
  }

  /** Change a release's configuration. Only accepted while the job is idle. */
  updateJob(jobId: string, update: JobUpdate): Observable<Job> {
    return this.http.patch<Job>(`${this.apiUrl}/${jobId}`, update);
  }

  moveItem(jobId: string, itemId: string, move: { group_name?: string; position?: number }): Observable<ReleaseNoteItem[]> {
    return this.http.post<ReleaseNoteItem[]>(`${this.apiUrl}/${jobId}/items/${itemId}/move`, move);
  }

  getTopics(jobId: string, render = true): Observable<ReleaseNoteTopic[]> {
    const params = new HttpParams().set('render', String(render));
    return this.http.get<ReleaseNoteTopic[]>(`${this.apiUrl}/${jobId}/topics`, { params });
  }

  reassembleTopics(jobId: string, strategy: ChunkingStrategy): Observable<ReleaseNoteTopic[]> {
    return this.http.post<ReleaseNoteTopic[]>(`${this.apiUrl}/${jobId}/topics/reassemble`, { chunking_strategy: strategy });
  }

  downloadTopic(jobId: string, topicId: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${jobId}/topics/${topicId}/download`, { responseType: 'blob' });
  }

  /**
   * Publish. `folderId` sends this one publish somewhere else, and `credentialId` is the
   * Heretto that folder is in — a folder id chosen in one connection means nothing in
   * another, so the two always travel together.
   */
  publish(jobId: string, folderId?: string, credentialId?: string): Observable<PublishResponse> {
    return this.http.post<PublishResponse>(`${this.apiUrl}/${jobId}/publish`,
      folderId ? { folder_id: folderId, credential_id: credentialId ?? null } : {});
  }

  getChat(jobId: string): Observable<ChatMessage[]> {
    return this.http.get<ChatMessage[]>(`${this.apiUrl}/${jobId}/chat`);
  }

  sendChat(jobId: string, message: string, selectedItemId?: string | null): Observable<ChatSendResponse> {
    return this.http.post<ChatSendResponse>(`${this.apiUrl}/${jobId}/chat`, {
      message,
      selected_item_id: selectedItemId || undefined,
    });
  }

  clearChat(jobId: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${jobId}/chat`);
  }
}
