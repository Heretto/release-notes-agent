import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { CredentialsService, JiraCredential, AICredential } from './credentials.service';
import { environment } from '../../../environments/environment';

describe('CredentialsService', () => {
  let service: CredentialsService;
  let httpMock: HttpTestingController;
  const apiUrl = `${environment.apiUrl}/credentials`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [CredentialsService]
    });
    service = TestBed.inject(CredentialsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  describe('Jira Credentials', () => {
    it('should fetch Jira credentials', () => {
      const mockCredentials: JiraCredential[] = [
        {
          id: '123',
          name: 'Test Jira',
          server_url: 'https://test.atlassian.net',
          email: 'test@example.com',
          api_token: 'token123'
        }
      ];

      service.getJiraCredentials().subscribe(credentials => {
        expect(credentials).toEqual(mockCredentials);
        expect(credentials.length).toBe(1);
        expect(credentials[0].name).toBe('Test Jira');
      });

      const req = httpMock.expectOne(`${apiUrl}/jira`);
      expect(req.request.method).toBe('GET');
      req.flush(mockCredentials);
    });

    it('should handle empty Jira credentials list', () => {
      service.getJiraCredentials().subscribe(credentials => {
        expect(credentials).toEqual([]);
        expect(credentials.length).toBe(0);
      });

      const req = httpMock.expectOne(`${apiUrl}/jira`);
      req.flush([]);
    });

    it('should create a new Jira credential', () => {
      const newCredential: JiraCredential = {
        name: 'New Jira',
        server_url: 'https://new.atlassian.net',
        email: 'new@example.com',
        api_token: 'new_token'
      };

      const createdCredential = { ...newCredential, id: '456' };

      service.createJiraCredential(newCredential).subscribe(credential => {
        expect(credential).toEqual(createdCredential);
        expect(credential.id).toBe('456');
      });

      const req = httpMock.expectOne(`${apiUrl}/jira`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(newCredential);
      req.flush(createdCredential);
    });

    it('should update an existing Jira credential', () => {
      const id = '123';
      const updateData: JiraCredential = {
        name: 'Updated Jira',
        server_url: 'https://updated.atlassian.net',
        email: 'updated@example.com',
        api_token: 'updated_token'
      };

      service.updateJiraCredential(id, updateData).subscribe(credential => {
        expect(credential).toEqual({ ...updateData, id });
      });

      const req = httpMock.expectOne(`${apiUrl}/jira/${id}`);
      expect(req.request.method).toBe('PUT');
      req.flush({ ...updateData, id });
    });

    it('should delete a Jira credential', () => {
      const id = '123';

      service.deleteJiraCredential(id).subscribe(response => {
        expect(response).toBeUndefined();
      });

      const req = httpMock.expectOne(`${apiUrl}/jira/${id}`);
      expect(req.request.method).toBe('DELETE');
      req.flush(null);
    });
  });

  describe('AI Credentials', () => {
    it('should fetch AI credentials', () => {
      const mockCredentials: AICredential[] = [
        {
          id: '789',
          name: 'OpenAI Key',
          provider: 'openai',
          api_key: 'sk-...',
          model: 'gpt-4'
        },
        {
          id: '790',
          name: 'Gemini Key',
          provider: 'gemini',
          api_key: 'AIza...',
          model: 'gemini-pro'
        }
      ];

      service.getAICredentials().subscribe(credentials => {
        expect(credentials).toEqual(mockCredentials);
        expect(credentials.length).toBe(2);
        expect(credentials[0].provider).toBe('openai');
        expect(credentials[1].provider).toBe('gemini');
      });

      const req = httpMock.expectOne(`${apiUrl}/ai`);
      expect(req.request.method).toBe('GET');
      req.flush(mockCredentials);
    });

    it('should fetch a single AI credential', () => {
      const id = '789';
      const mockCredential: AICredential = {
        id,
        name: 'OpenAI Key',
        provider: 'openai',
        api_key: 'sk-...',
        model: 'gpt-4'
      };

      service.getAICredential(id).subscribe(credential => {
        expect(credential).toEqual(mockCredential);
        expect(credential.id).toBe(id);
      });

      const req = httpMock.expectOne(`${apiUrl}/ai/${id}`);
      expect(req.request.method).toBe('GET');
      req.flush(mockCredential);
    });

    it('should create a new AI credential', () => {
      const newCredential: AICredential = {
        name: 'New AI Key',
        provider: 'anthropic',
        api_key: 'sk-ant-...',
        model: 'claude-3'
      };

      const createdCredential = { ...newCredential, id: '791' };

      service.createAICredential(newCredential).subscribe(credential => {
        expect(credential).toEqual(createdCredential);
        expect(credential.provider).toBe('anthropic');
      });

      const req = httpMock.expectOne(`${apiUrl}/ai`);
      expect(req.request.method).toBe('POST');
      req.flush(createdCredential);
    });

    it('should properly format update data for AI credentials', () => {
      const id = '789';
      const updateData = {
        name: 'Updated AI Key',
        api_key: 'new-key',
        model: 'gpt-4-turbo'
      };

      service.updateAICredential(id, updateData).subscribe();

      const req = httpMock.expectOne(`${apiUrl}/${id}`);
      expect(req.request.method).toBe('PUT');
      
      const sentData = req.request.body;
      expect(sentData.name).toBe('Updated AI Key');
      expect(sentData.credentials).toBeDefined();
      expect(sentData.credentials.api_key).toBe('new-key');
      expect(sentData.credentials.model).toBe('gpt-4-turbo');
      
      req.flush({ ...updateData, id });
    });

    it('should not include empty api_key in update', () => {
      const id = '789';
      const updateData = {
        name: 'Updated Name Only',
        model: 'new-model'
      };

      service.updateAICredential(id, updateData).subscribe();

      const req = httpMock.expectOne(`${apiUrl}/${id}`);
      const sentData = req.request.body;
      expect(sentData.credentials).toBeDefined();
      expect(sentData.credentials.api_key).toBeUndefined();
      expect(sentData.credentials.model).toBe('new-model');
      
      req.flush({ ...updateData, id });
    });
  });

  describe('Test Credential', () => {
    it('should test a credential connection', () => {
      const id = '123';
      const mockResponse = {
        success: true,
        status_code: 200,
        message: 'Connection successful',
        timestamp: new Date().toISOString()
      };

      service.testCredential(id).subscribe(response => {
        expect(response).toEqual(mockResponse);
        expect(response.success).toBe(true);
        expect(response.status_code).toBe(200);
      });

      const req = httpMock.expectOne(`${apiUrl}/${id}/test`);
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({});
      req.flush(mockResponse);
    });

    it('should handle test failure', () => {
      const id = '123';
      const mockResponse = {
        success: false,
        status_code: 401,
        message: 'Authentication failed',
        error: 'Invalid API key'
      };

      service.testCredential(id).subscribe(response => {
        expect(response.success).toBe(false);
        expect(response.status_code).toBe(401);
        expect(response.error).toBe('Invalid API key');
      });

      const req = httpMock.expectOne(`${apiUrl}/${id}/test`);
      req.flush(mockResponse);
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors when fetching credentials', () => {
      const errorMessage = 'Network error';

      service.getJiraCredentials().subscribe(
        () => fail('should have failed'),
        error => {
          expect(error.status).toBe(500);
          expect(error.statusText).toBe(errorMessage);
        }
      );

      const req = httpMock.expectOne(`${apiUrl}/jira`);
      req.flush(null, { status: 500, statusText: errorMessage });
    });

    it('should handle 404 errors when credential not found', () => {
      const id = 'non-existent';

      service.deleteJiraCredential(id).subscribe(
        () => fail('should have failed'),
        error => {
          expect(error.status).toBe(404);
        }
      );

      const req = httpMock.expectOne(`${apiUrl}/jira/${id}`);
      req.flush(null, { status: 404, statusText: 'Not Found' });
    });
  });
});