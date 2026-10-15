import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { HopCredentialService } from '@heretto/hop-ui';

/**
 * The Jira credential pickers this app shows outside the credentials page: the connection an
 * instruction set runs its query against, and the one the JQL test dialog uses.
 *
 * Managing credentials is hop-core's — `HopCredentialsComponent` renders the page and
 * `HopCredentialService` talks to the generic `/credentials` API. This only reshapes what
 * that returns, so a caller does not have to know a Jira server URL arrives inside `values`.
 *
 * There is deliberately no AI-credential picker here: an agent names the AI configuration it
 * runs on (hop-core's agent editor selects it), so nothing in this app picks one directly.
 */

export interface JiraCredentialOption {
  id: string;
  name: string;
  server_url: string;
}

@Injectable({ providedIn: 'root' })
export class CredentialsService {
  private credentials = inject(HopCredentialService);

  getJiraCredentials(): Observable<JiraCredentialOption[]> {
    return this.credentials.listCredentials().pipe(
      map(all => all
        .filter(credential => credential.type === 'jira')
        .map(credential => ({
          id: credential.id,
          name: credential.name,
          server_url: (credential.values?.['server_url'] as string) || '',
        }))
      )
    );
  }
}
