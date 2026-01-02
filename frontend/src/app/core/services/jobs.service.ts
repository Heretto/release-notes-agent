import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface JobCreate {
  jql_query: string;
  instruction_set_id: string;
  ai_credential_id?: string;
  additional_instructions?: string;
  output_filename: string;
  publish_to_heretto: boolean;
  heretto_folder_id?: string;
  max_tickets?: number;
}

export interface Job {
  id: string;
  user_id: string;
  instruction_set_id?: string;
  ai_credential_id?: string;
  jql_query: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  triggered_by: 'manual' | 'webhook' | 'scheduled';
  output_filename?: string;
  tickets_processed: number;
  max_tickets?: number;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

@Injectable({
  providedIn: 'root'
})
export class JobsService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/jobs`;

  getJobs(status?: string): Observable<Job[]> {
    if (status) {
      return this.http.get<Job[]>(`${this.apiUrl}/`, { params: { status } });
    }
    return this.http.get<Job[]>(`${this.apiUrl}/`);
  }

  getJob(id: string): Observable<Job> {
    return this.http.get<Job>(`${this.apiUrl}/${id}`);
  }

  createJob(job: JobCreate): Observable<Job> {
    return this.http.post<Job>(`${this.apiUrl}/`, job);
  }

  cancelJob(id: string): Observable<void> {
    return this.http.post<void>(`${this.apiUrl}/${id}/cancel`, {});
  }

  retryJob(id: string): Observable<Job> {
    return this.http.post<Job>(`${this.apiUrl}/${id}/retry`, {});
  }

  getJobArtifacts(id: string): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/${id}/artifacts`);
  }

  getArtifactContent(jobId: string, artifactId: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/${jobId}/artifacts/${artifactId}/content`);
  }

  downloadArtifact(jobId: string, artifactId: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${jobId}/artifacts/${artifactId}/download`, {
      responseType: 'blob'
    });
  }

  getJobRequests(jobId: string): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/${jobId}/requests`);
  }

  deleteArtifact(jobId: string, artifactId: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${jobId}/artifacts/${artifactId}`);
  }

  deleteAllArtifacts(jobId: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${jobId}/artifacts`);
  }

  rerunJob(id: string): Observable<Job> {
    return this.http.post<Job>(`${this.apiUrl}/${id}/rerun`, {});
  }
}