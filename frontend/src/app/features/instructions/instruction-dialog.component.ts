import { Component, Inject, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { Subscription, debounceTime, distinctUntilChanged } from 'rxjs';
import { RouterLink } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule, FormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { HopAgentService, AgentSummary } from '@heretto/hop-ui';
import { DEFAULT_LAYOUT, STARTER_TEMPLATE, InstructionSet, InstructionsService, JiraRelease } from '../../core/services/instructions.service';
import { CredentialsService, JiraCredentialOption } from '../../core/services/credentials.service';
import { CHUNKING_STRATEGIES } from '../../core/services/jobs.service';
import { JqlPart, JqlVariableSpec, defaultsOf, jqlParts, variableNames } from '../../core/jql-variables';

/** The releases card opens on the most recent few; everything older is a press away. */
const FIRST_RELEASES = 5;
const MORE_RELEASES = 10;

@Component({
  selector: 'app-instruction-dialog',
  standalone: true,
  imports: [
    RouterLink,
    ReactiveFormsModule,
    FormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSlideToggleModule,
    MatCheckboxModule,
    MatExpansionModule,
    MatIconModule,
    MatTooltipModule,
    MatSelectModule,
    MatButtonToggleModule
  ],
  template: `
    <h2 mat-dialog-title>
      {{ data?.id ? 'Edit' : 'Create' }} Instruction Set
    </h2>

    <mat-dialog-content>
      <form [formGroup]="form">
        <div class="form-section">
          <h3>Basic information</h3>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Name</mat-label>
            <input matInput formControlName="name" required>
            @if (form.get('name')?.hasError('required')) {
              <mat-error>Name is required</mat-error>
            }
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Description</mat-label>
            <textarea matInput formControlName="description" rows="2"></textarea>
            <mat-hint>Brief description of what this instruction set does</mat-hint>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Product name</mat-label>
            <input matInput formControlName="product_name" placeholder="e.g. Heretto CCMS">
            <mat-hint>Used in topic titles and when the agents talk about the product</mat-hint>
          </mat-form-field>

          <div class="default-toggle">
            <mat-slide-toggle formControlName="is_default">
              Set as default instruction set
            </mat-slide-toggle>
            <mat-icon
              matTooltip="Default instruction sets are pre-selected when creating new jobs"
              class="info-icon">
              info
            </mat-icon>
          </div>
        </div>

        <div class="form-section">
          <h3>Jira</h3>

          @if (jiraCredentials.length === 0) {
            <div class="hint-box">
              <mat-icon>info</mat-icon>
              <span>No Jira credentials yet. Add one in the Credentials page first.</span>
            </div>
          }

          @if (jiraCredentials.length > 0) {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Jira credential</mat-label>
              <mat-select formControlName="jira_credential_id">
                <mat-option [value]="null">Use any available (org default)</mat-option>
                @for (cred of jiraCredentials; track cred.id) {
                  <mat-option [value]="cred.id">
                    {{ cred.name }} ({{ cred.server_url }})
                  </mat-option>
                }
              </mat-select>
              <mat-hint>Which Jira connection this instruction set's query runs against</mat-hint>
            </mat-form-field>
          }

          <div class="source-switch">
            <span class="source-label">Source</span>
            <mat-button-toggle-group formControlName="source_mode" aria-label="Issue source">
              <mat-button-toggle value="jql">JQL query</mat-button-toggle>
              <mat-button-toggle value="releases">Jira releases</mat-button-toggle>
            </mat-button-toggle-group>
            <p class="muted source-help">
              @if (isReleasesMode) {
                The agent reads the releases (fix versions) Jira tracks for a project. You pick one when you start a release.
              } @else {
                Write the query yourself, with variables for anything that changes per release.
              }
            </p>
          </div>

          @if (isReleasesMode) {
            <!-- subscriptSizing="dynamic": the hint wraps in a half-width field, and the
                 default fixed one-line subscript lets it run into the card below. -->
            <div class="two-up">
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Project key</mat-label>
                <input matInput class="mono upper" formControlName="jira_project" placeholder="HER" required>
                @if (form.get('jira_project')?.hasError('required')) {
                  <mat-error>A Jira project key is required</mat-error>
                }
              </mat-form-field>

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Additional filter</mat-label>
                <input matInput class="mono" formControlName="extra_jql" placeholder="status in (Done, Released)">
                <mat-hint>Optional JQL added to every release query</mat-hint>
              </mat-form-field>
            </div>

            <div class="vars-card">
              <div class="vars-head">
                <span class="vars-title">Releases detected</span>
                <span class="muted">{{ releasesStatus }}</span>
              </div>
              @if (releases.length) {
                <div class="release-list">
                  @for (release of releases; track release.name) {
                    <div class="release-row">
                      <span class="release-name">{{ release.name }}</span>
                      <span class="release-chip" [class.released]="release.released">
                        {{ release.released ? 'Released' : 'Unreleased' }}
                      </span>
                      <span class="release-date">{{ releaseDateText(release) }}</span>
                      <span class="release-count">{{ release.issue_count }} issues</span>
                    </div>
                  }
                </div>
              }
              @if (releasesHasMore) {
                <button type="button" class="load-more" (click)="loadMoreReleases()" [disabled]="loadingReleases">
                  {{ loadingReleases ? 'Loading…' : 'Load ' + nextBatchSize + ' more' }}
                </button>
              }
              <div class="vars-preview">
                <span class="vars-col">Query for each release</span>
                <div class="query-preview">{{ releaseQueryPreview }}</div>
              </div>
            </div>
          } @else {
          <!-- subscriptSizing="dynamic": the hint wraps to two lines, and the default fixed
               one-line subscript lets it run into the Variables card below. -->
          <mat-form-field appearance="outline" class="full-width jql-field" subscriptSizing="dynamic">
            <mat-label>JQL query</mat-label>
            <textarea matInput formControlName="jql_query" rows="3" required
                      placeholder="e.g., project = MYPROJECT AND fixVersion = '1.0' ORDER BY created DESC"></textarea>
            @if (form.get('jql_query')?.hasError('required')) {
              <mat-error>JQL query is required</mat-error>
            }
            <mat-hint>Selects the issues a job evaluates for release notes. Wrap anything that changes per release in braces — <code>&#123;version&#125;</code> — to make it a variable.</mat-hint>
          </mat-form-field>

          <div class="vars-card">
            <div class="vars-head">
              <span class="vars-title">Variables</span>
              <span class="muted">
                {{ variableNames.length ? variableNames.length + ' found in the query' : 'None found in the query' }}
              </span>
            </div>

            @if (variableNames.length) {
              <div class="vars-grid">
                <span class="vars-col">Variable</span>
                <span class="vars-col">Label</span>
                <span class="vars-col">Default value</span>
                <span class="vars-col">Hint</span>
                @for (name of variableNames; track name) {
                  <code class="var-token">{{ token(name) }}</code>
                  <input class="var-input" [ngModel]="variableSpecs[name].label" [ngModelOptions]="{standalone: true}"
                         (ngModelChange)="setVariable(name, 'label', $event)" [placeholder]="name">
                  <input class="var-input mono" [ngModel]="variableSpecs[name].default" [ngModelOptions]="{standalone: true}"
                         (ngModelChange)="setVariable(name, 'default', $event)" placeholder="Optional">
                  <input class="var-input" [ngModel]="variableSpecs[name].hint" [ngModelOptions]="{standalone: true}"
                         (ngModelChange)="setVariable(name, 'hint', $event)" placeholder="Where to find this value">
                }
              </div>

              <div class="vars-preview">
                <span class="vars-col">Query with defaults</span>
                <div class="query-preview">
                  @for (part of previewParts; track $index) {
                    @if (part.isVar) {
                      <span class="chip-filled">{{ part.text }}</span>
                    } @else if (part.isEmpty) {
                      <span class="chip-missing" matTooltip="No default — whoever starts a release fills this in">{{ part.text }}</span>
                    } @else {
                      <span>{{ part.text }}</span>
                    }
                  }
                </div>
              </div>
            } @else {
              <p class="muted vars-empty">
                No variables yet. Example: <code>fixVersion = &#123;version&#125; ORDER BY created ASC</code>
              </p>
            }
          </div>

          }

          @if (!isReleasesMode) {
          <mat-expansion-panel class="jql-help">
            <mat-expansion-panel-header>
              <mat-panel-title>
                <mat-icon>help</mat-icon>
                JQL query examples
              </mat-panel-title>
            </mat-expansion-panel-header>
            <div class="jql-examples">
              <ul>
                <li><code>project = PROJ AND fixVersion = "1.0"</code> — all tickets for version 1.0</li>
                <li><code>project = PROJ AND status = Done AND resolved >= -30d</code> — recently completed tickets</li>
                <li><code>project = PROJ AND labels = "release-notes"</code> — tickets tagged for release notes</li>
                <li><code>project = PROJ AND component = "Backend" ORDER BY priority DESC</code> — one component, by priority</li>
              </ul>
            </div>
          </mat-expansion-panel>
          }
        </div>

        <div class="form-section">
          <h3>Agents</h3>
          <p class="section-hint">
            The writer drafts every release note as DITA and is the agent you work with in the
            workspace. The analysis agent decides which issues matter and how the notes are
            organized; leave it unset to use the writer for both.
          </p>

          @if (agents.length === 0) {
            <div class="hint-box">
              <mat-icon>info</mat-icon>
              <span>No agents yet. <a routerLink="/agents">Create one</a> to get started.</span>
            </div>
          }

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Writer agent</mat-label>
            <mat-select formControlName="writer_agent_id" required>
              @for (agent of agents; track agent.id) {
                <mat-option [value]="agent.id">
                  {{ agent.name }}@if (!agent.ai_configuration) { <span class="muted"> (no AI configuration)</span> }
                </mat-option>
              }
            </mat-select>
            @if (form.get('writer_agent_id')?.hasError('required')) {
              <mat-error>A writer agent is required</mat-error>
            }
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Analysis agent</mat-label>
            <mat-select formControlName="analysis_agent_id">
              <mat-option [value]="null">Same as the writer</mat-option>
              @for (agent of agents; track agent.id) {
                <mat-option [value]="agent.id">{{ agent.name }}</mat-option>
              }
            </mat-select>
            <mat-hint>Evaluates issues and organizes the notes</mat-hint>
          </mat-form-field>
        </div>

        <div class="form-section">
          <h3>Guidance</h3>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>What counts as a change users need to know about</mat-label>
            <textarea matInput formControlName="relevance_guidance" rows="3"
                      placeholder="e.g. Anything that changes the UI, an API response, a default, or a limit. Internal refactors and test work are not relevant."></textarea>
            <mat-hint>Shown to the analysis agent when it decides which issues become release notes</mat-hint>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>How the release notes are organized and written</mat-label>
            <textarea matInput formControlName="organization_guidance" rows="4"
                      placeholder="e.g. Group as New features, Improvements, Fixes, then Known issues. Open every note with Added. / Changed. / Fixed. and write in past simple."></textarea>
            <mat-hint>
              Given to the agent that groups the notes and to the one that writes them. Rules about
              the topic around a note — its title, shortdesc or sections — are set by Topics below,
              not here.
            </mat-hint>
          </mat-form-field>
        </div>

        <div class="form-section">
          <h3>Output</h3>

          <div class="layout-card">
            <div class="vars-head">
              <span class="vars-title">Topic layout</span>
              <span class="muted">The shape of the DITA this instruction set produces</span>
            </div>

            <mat-button-toggle-group formControlName="layout_mode" class="layout-modes"
                                     aria-label="How the topic structure is decided">
              <mat-button-toggle value="structured">Choose a pattern</mat-button-toggle>
              <mat-button-toggle value="template">Write a DITA template</mat-button-toggle>
              <mat-button-toggle value="agent">Describe it</mat-button-toggle>
            </mat-button-toggle-group>
            <p class="muted mode-help">
              @switch (form.get('layout_mode')?.value) {
                @case ('template') {
                  Your own DITA topic, emitted as written. Mark where the notes go and what
                  repeats per group; everything else — fixed paragraphs, conkeyrefs, a
                  populated shortdesc — comes through untouched.
                }
                @case ('agent') {
                  Describe the structure in your own words. At the start of each release an
                  agent turns it into a template, which that release then keeps — so the
                  shape stays put while you edit notes.
                }
                @default {
                  Pick from the shapes this app can build. Always valid, nothing to author.
                }
              }
            </p>

            @if (form.get('layout_mode')?.value === 'structured') {
            <div class="layout-grid">
              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Each group starts with</mat-label>
                <mat-select formControlName="group_heading">
                  <mat-option value="section">A section with a title</mat-option>
                  <mat-option value="paragraph">A bold paragraph</mat-option>
                  <mat-option value="none">Nothing</mat-option>
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Its notes are collected in</mat-label>
                <mat-select formControlName="notes_wrapper">
                  <mat-option value="none">Nothing</mat-option>
                  <mat-option value="ul">A bulleted list</mat-option>
                  <mat-option value="ol">A numbered list</mat-option>
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Each note is</mat-label>
                <mat-select formControlName="note_element">
                  <mat-option value="div">A block (&lt;div&gt;)</mat-option>
                  <mat-option value="li">A list item (&lt;li&gt;)</mat-option>
                </mat-select>
                @if (form.get('note_element')?.value === 'li') {
                  <mat-hint>List items need a list, so the notes are collected in one</mat-hint>
                }
              </mat-form-field>

              <mat-form-field appearance="outline" subscriptSizing="dynamic">
                <mat-label>Short description</mat-label>
                <mat-select formControlName="shortdesc">
                  <mat-option value="omit">Leave it out</mat-option>
                  <mat-option value="empty">Empty, for the writer to fill in</mat-option>
                  <mat-option value="text">Always the same text</mat-option>
                </mat-select>
              </mat-form-field>
            </div>

            @if (form.get('shortdesc')?.value === 'text') {
              <mat-form-field appearance="outline" class="full-width" subscriptSizing="dynamic">
                <mat-label>Short description text</mat-label>
                <input matInput formControlName="shortdesc_text">
              </mat-form-field>
            }

            <div class="vars-preview">
              <span class="vars-col">A topic will look like</span>
              <pre class="query-preview layout-preview">{{ layoutPreview }}</pre>
            </div>
            }

            @if (form.get('layout_mode')?.value === 'template') {
              <mat-form-field appearance="outline" class="full-width" subscriptSizing="dynamic">
                <mat-label>DITA topic template</mat-label>
                <textarea matInput class="mono" formControlName="template_dita" rows="12"
                          spellcheck="false"></textarea>
                @if (templateProblems.length) {
                  <mat-error>{{ templateProblems[0] }}</mat-error>
                }
              </mat-form-field>
              <ul class="marker-help muted">
                <li><code>outputclass="rn-notes"</code> — the element the notes go inside. A
                  <code>&lt;ul&gt;</code> or <code>&lt;ol&gt;</code> makes each note an
                  <code>&lt;li&gt;</code>; anything else makes it a <code>&lt;div&gt;</code>.</li>
                <li><code>outputclass="rn-group"</code> — the element repeated once per group,
                  with the notes marker inside it. Leave it out if you do not group notes.</li>
                <li><code>&#123;title&#125;</code> and <code>&#123;group&#125;</code> are replaced as the topic is built.</li>
              </ul>
            }

            @if (form.get('layout_mode')?.value === 'agent') {
              <mat-form-field appearance="outline" class="full-width" subscriptSizing="dynamic">
                <mat-label>Describe the structure</mat-label>
                <textarea matInput formControlName="agent_guidance" rows="8"
                          placeholder="e.g. One bold paragraph per product release with the product name and version, then that product's notes as a single bulleted list. Leave the short description empty."></textarea>
                <mat-hint>
                  Turned into a template when a release starts, and kept for that release.
                  Until the first run, releases from this set use the default shape.
                </mat-hint>
              </mat-form-field>
            }
          </div>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Topics</mat-label>
            <mat-select formControlName="chunking_strategy">
              @for (strategy of chunkingStrategies; track strategy.value) {
                <mat-option [value]="strategy.value">{{ strategy.label }} — {{ strategy.hint }}</mat-option>
              }
            </mat-select>
            <mat-hint>How release notes are split into DITA topics by default; it can be changed per job</mat-hint>
          </mat-form-field>

          <div class="heretto-toggle">
            <mat-checkbox formControlName="publish_to_heretto">
              Publish topics to Heretto when a run finishes
            </mat-checkbox>
          </div>

          @if (form.get('publish_to_heretto')?.value) {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Heretto folder ID</mat-label>
              <input matInput formControlName="heretto_folder_id"
                     placeholder="e.g., 12345-abcde-67890">
              <mat-hint>Target folder in Heretto where the topics are created</mat-hint>
            </mat-form-field>
          }
        </div>
      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
      <button mat-raised-button color="primary"
              [disabled]="!form.valid"
              (click)="onSave()">
        {{ data?.id ? 'Update' : 'Create' }}
      </button>
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    .source-switch { margin-bottom: 16px; }
    .source-label { display: block; font-size: 12px; font-weight: 500; color: var(--text-secondary); margin-bottom: 6px; }
    .source-help { margin: 6px 0 0; font-size: 12px; }
    .two-up { display: grid; grid-template-columns: 160px 1fr; gap: 12px; align-items: start; margin-bottom: 18px; }
    .two-up mat-form-field { width: 100%; }
    .upper { text-transform: uppercase; }
    .release-list { display: flex; flex-direction: column; gap: 6px; }
    .release-row { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border: 1px solid var(--border-default);
      border-radius: 6px; background: var(--bg-primary); }
    .release-name { font-family: var(--font-mono); font-size: 13px; font-weight: 600; min-width: 72px; }
    .release-chip { display: inline-flex; align-items: center; font-size: 11px; font-weight: 600; padding: 4px 8px;
      border-radius: 999px; background: var(--color-info-bg, var(--bg-secondary)); color: var(--color-info-text, var(--text-secondary)); }
    .release-chip.released { background: var(--color-success-bg); color: var(--color-success-text); }
    .release-date { flex: 1; font-size: 12px; color: var(--text-tertiary); }
    .release-count { font-size: 12px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
    .load-more { align-self: flex-start; background: none; border: none; padding: 6px 2px 0; cursor: pointer;
      font: inherit; font-size: 13px; font-weight: 500; color: var(--color-primary); }
    .load-more:disabled { color: var(--text-tertiary); cursor: default; }
    .jql-field { margin-bottom: 12px; }
    .layout-card { border: 1px solid var(--border-default); border-radius: 8px; padding: 12px 14px;
      margin-bottom: 16px; background: var(--bg-secondary); }
    .layout-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px; align-items: start; margin-bottom: 10px; }
    .layout-grid mat-form-field { width: 100%; }
    .layout-preview { margin: 0; white-space: pre; overflow-x: auto; }
    .layout-modes { margin-bottom: 8px; }
    .mode-help { margin: 0 0 12px; font-size: 12px; line-height: 1.5; max-width: 66ch; }
    .marker-help { margin: 2px 0 0; padding-left: 18px; font-size: 12px; line-height: 1.6; }
    .marker-help code { font-family: var(--font-mono); font-size: 11px; }
    .vars-card { border: 1px solid var(--border-default); border-radius: 8px; padding: 12px 14px; margin-bottom: 16px; background: var(--bg-secondary); }
    .vars-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; }
    .vars-title { font-size: 13px; font-weight: 600; }
    .vars-grid { display: grid; grid-template-columns: 130px 1fr 1fr 1.3fr; gap: 6px 8px; align-items: center; }
    .vars-col { font-size: 11px; font-weight: 600; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.03em; }
    .var-token { font-family: var(--font-mono); font-size: 12px; font-weight: 600; padding: 6px 8px; border-radius: 4px;
      background: var(--color-accent-bg, var(--bg-primary)); color: var(--color-accent-text, var(--text-primary));
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .var-input { font: inherit; font-size: 13px; padding: 6px 8px; border: 1px solid var(--border-default);
      border-radius: 4px; background: var(--bg-primary); color: var(--text-primary); min-width: 0; }
    .var-input.mono { font-family: var(--font-mono); }
    .var-input:focus { outline: none; border-color: var(--color-primary); }
    .vars-preview { margin-top: 12px; display: flex; flex-direction: column; gap: 4px; }
    .query-preview { background: var(--bg-primary); border: 1px solid var(--border-default); border-radius: 6px;
      padding: 8px 10px; font-family: var(--font-mono); font-size: 12px; line-height: 1.6; word-break: break-word; }
    .chip-filled { background: var(--color-primary-bg); color: var(--color-primary-text); font-weight: 600; padding: 0 5px; border-radius: 4px; }
    .chip-missing { background: var(--color-error-bg); color: var(--color-error-text); font-weight: 600; padding: 0 5px; border-radius: 4px; }
    .vars-empty { font-size: 13px; margin: 0; }
    .vars-empty code, mat-hint code { font-family: var(--font-mono); font-size: 12px; }
    mat-dialog-content { min-width: 600px; max-width: 800px; max-height: 70vh; overflow-y: auto; }
    .form-section { margin-bottom: 28px; }
    .form-section h3 { color: var(--text-primary); margin-bottom: 8px; font-size: 16px; font-weight: 500; }
    .full-width { width: 100%; }
    .default-toggle { display: flex; align-items: center; gap: 10px; margin: 15px 0; }
    .heretto-toggle { margin: 12px 0; }
    .info-icon { font-size: 18px; color: var(--text-tertiary); cursor: help; }
    .jql-help { margin: 15px 0; background: var(--bg-secondary); box-shadow: none !important; }
    .jql-examples { padding: 15px; font-size: 14px; }
    .jql-examples ul { margin: 0; padding-left: 20px; }
    .jql-examples li { margin: 8px 0; }
    .jql-examples code { background: var(--bg-secondary); padding: 2px 6px; border-radius: 3px; font-family: var(--font-mono); font-size: 13px; }
    .section-hint { color: var(--text-secondary); font-size: 13px; margin: 0 0 15px 0; }
    .hint-box { display: flex; align-items: center; gap: 8px; background: var(--bg-secondary); padding: 10px 14px; border-radius: 4px; font-size: 14px; margin-bottom: 15px; }
    .muted { color: var(--text-tertiary); }
    mat-expansion-panel-header { padding-left: 0 !important; }
    mat-panel-title { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 14px; }
    mat-panel-title mat-icon { font-size: 20px; }
  `]
})
export class InstructionDialogComponent implements OnInit {
  form: FormGroup;
  agents: AgentSummary[] = [];
  jiraCredentials: JiraCredentialOption[] = [];
  chunkingStrategies = CHUNKING_STRATEGIES;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<InstructionDialogComponent>,
    private agentService: HopAgentService,
    private credentialsService: CredentialsService,
    private instructionsService: InstructionsService,
    @Inject(MAT_DIALOG_DATA) public data: InstructionSet | null
  ) {
    this.variableSpecs = { ...(data?.variables || {}) };
    const layout = { ...DEFAULT_LAYOUT, ...(data?.layout?.structured || {}) };
    this.form = this.fb.group({
      name: [data?.name || '', Validators.required],
      description: [data?.description || ''],
      product_name: [data?.product_name || ''],
      source_mode: [data?.source_mode || 'jql'],
      jira_project: [data?.jira_project || ''],
      extra_jql: [data?.extra_jql || ''],
      jql_query: [data?.jql_query || ''],
      jira_credential_id: [data?.jira_credential_id || null],
      writer_agent_id: [data?.writer_agent_id || null, Validators.required],
      analysis_agent_id: [data?.analysis_agent_id || null],
      relevance_guidance: [data?.relevance_guidance || ''],
      organization_guidance: [data?.organization_guidance || ''],
      chunking_strategy: [data?.chunking_strategy || 'single'],
      group_heading: [layout.group_heading],
      notes_wrapper: [layout.notes_wrapper],
      note_element: [layout.note_element],
      shortdesc: [layout.shortdesc],
      shortdesc_text: [layout.shortdesc_text],
      layout_mode: [data?.layout?.mode || 'structured'],
      template_dita: [data?.layout?.template?.dita || ''],
      agent_guidance: [data?.layout?.agent?.guidance || ''],
      heretto_folder_id: [data?.heretto_folder_id || ''],
      publish_to_heretto: [data?.publish_to_heretto || false],
      is_default: [data?.is_default || false]
    });
  }

  /** Jira's releases for the project key typed above, in "releases" mode. */
  releases: JiraRelease[] = [];
  releasesStatus = '';
  releasesHasMore = false;
  loadingReleases = false;
  private releasesTotal = 0;
  private releasesNextStart = 0;
  private releasesRequest?: Subscription;

  /** The card opens on the most recent few; everything older is a press away. */
  get nextBatchSize(): number {
    return Math.min(MORE_RELEASES, Math.max(this.releasesTotal - this.releases.length, 1));
  }

  get isReleasesMode(): boolean {
    return this.form?.get('source_mode')?.value === 'releases';
  }

  /** The query every release in this mode runs, with the release name standing in. */
  get releaseQueryPreview(): string {
    const project = (this.form?.get('jira_project')?.value || '').trim().toUpperCase();
    const extra = (this.form?.get('extra_jql')?.value || '').trim();
    if (!project) return 'Enter a project key to see the query each release will run.';
    return `project = ${project} AND fixVersion = "…"${extra ? ` AND (${extra})` : ''} ORDER BY created ASC`;
  }

  releaseDateText(release: JiraRelease): string {
    if (!release.date) return '';
    return `${release.released ? 'Released ' : 'Due '}${release.date}`;
  }

  /**
   * Jira is the only place a release list exists, so it is read live. Only a saved
   * instruction set can be asked — the endpoint resolves the Jira credential from the
   * stored row — so a new one shows the project key's query and nothing else until saved.
   */
  private loadReleases(): void {
    if (!this.isReleasesMode) return;
    const project = (this.form.get('jira_project')?.value || '').trim();
    this.releases = [];
    this.releasesTotal = 0;
    this.releasesNextStart = 0;
    this.releasesHasMore = false;
    if (!project) {
      this.releasesStatus = '';
      return;
    }
    if (!this.data?.id) {
      this.releasesStatus = 'Save the instruction set to see its releases';
      return;
    }
    this.fetchReleases(FIRST_RELEASES);
  }

  loadMoreReleases(): void {
    if (!this.loadingReleases) this.fetchReleases(MORE_RELEASES);
  }

  private fetchReleases(count: number): void {
    if (!this.data?.id) return;
    this.loadingReleases = true;
    if (!this.releases.length) this.releasesStatus = 'Loading…';
    this.releasesRequest?.unsubscribe();
    this.releasesRequest = this.instructionsService
      .listReleases(this.data.id, this.releasesNextStart, count)
      .subscribe({
        next: result => {
          this.loadingReleases = false;
          this.releases = [...this.releases, ...result.releases];
          this.releasesTotal = result.total;
          this.releasesNextStart = result.next_start;
          this.releasesHasMore = result.has_more;
          this.releasesStatus = this.releases.length
            ? `${this.releases.length} of ${result.total} in ${result.project}`
            : `No releases found in ${result.project}.`;
        },
        error: error => {
          this.loadingReleases = false;
          this.releasesHasMore = false;
          this.releasesStatus = error.error?.detail || 'Could not read releases from Jira';
        }
      });
  }

  /**
   * What is wrong with the template, in the words the API would use. Checked here so the
   * problem shows while it is being written rather than on save.
   */
  get templateProblems(): string[] {
    if (this.form?.get('layout_mode')?.value !== 'template') return [];
    const dita = (this.form.get('template_dita')?.value || '').trim();
    if (!dita) return ['Write the DITA template, or choose another layout mode.'];

    const problems: string[] = [];
    const parsed = new DOMParser().parseFromString(dita, 'application/xml');
    if (parsed.querySelector('parsererror')) return ['That is not well-formed XML.'];
    const root = parsed.documentElement;
    if (root.nodeName !== 'topic') problems.push(`The template must be a <topic>; this one is a <${root.nodeName}>.`);
    if (!this.hasMarker(root, 'rn-notes')) {
      problems.push('Nothing says where the notes go. Put outputclass="rn-notes" on the element that should hold them.');
    }
    if (!root.querySelector('title')) problems.push('The template needs a <title>.');
    return problems;
  }

  private hasMarker(root: Element, marker: string): boolean {
    for (const el of Array.from(root.getElementsByTagName('*'))) {
      if ((el.getAttribute('outputclass') || '').split(/\s+/).includes(marker)) return true;
    }
    return (root.getAttribute('outputclass') || '').split(/\s+/).includes(marker);
  }

  /**
   * The DITA skeleton the current choices produce — the same shape build_topic_xml emits,
   * written out so a choice can be judged without starting a release to see it.
   */
  get layoutPreview(): string {
    const heading = this.form?.get('group_heading')?.value;
    const wrapper = this.form?.get('notes_wrapper')?.value;
    const note = this.form?.get('note_element')?.value;
    const shortdesc = this.form?.get('shortdesc')?.value;

    const lines = ['<topic>', '  <title>Release notes</title>'];
    if (shortdesc === 'empty') lines.push('  <shortdesc/>');
    if (shortdesc === 'text') lines.push(`  <shortdesc>${this.form?.get('shortdesc_text')?.value || '…'}</shortdesc>`);
    lines.push('  <body>');

    const indent = heading === 'section' ? '      ' : '    ';
    if (heading === 'section') {
      lines.push('    <section>', '      <title>New features</title>');
    } else if (heading === 'paragraph') {
      lines.push('    <p><b>New features</b></p>');
    }
    if (wrapper !== 'none') lines.push(`${indent}<${wrapper}>`);
    const noteIndent = wrapper === 'none' ? indent : indent + '  ';
    lines.push(`${noteIndent}<${note} outputclass="release-note">…the note…</${note}>`);
    if (wrapper !== 'none') lines.push(`${indent}</${wrapper}>`);
    if (heading === 'section') lines.push('    </section>');

    lines.push('  </body>', '</topic>');
    return lines.join('\n');
  }

  /** Spec metadata per variable, kept for tokens that come and go while editing. */
  variableSpecs: Record<string, JqlVariableSpec> = {};

  /** The tokens currently in the query — the editor rows follow this, not the stored keys. */
  get variableNames(): string[] {
    const names = variableNames(this.form?.get('jql_query')?.value || '');
    // A token typed just now has no spec yet; give it a blank one so the row can bind.
    for (const name of names) {
      if (!this.variableSpecs[name]) this.variableSpecs[name] = { label: '', default: '', hint: '' };
    }
    return names;
  }

  /** The query as it would run using each variable's default. */
  get previewParts(): JqlPart[] {
    return jqlParts(this.form?.get('jql_query')?.value || '', defaultsOf(this.variableSpecs));
  }

  /** The literal token text. Built here because `&#123;{{ name }}` confuses the template parser. */
  token(name: string): string {
    return `{${name}}`;
  }

  setVariable(name: string, field: keyof JqlVariableSpec, value: string): void {
    this.variableSpecs[name] = { ...this.variableSpecs[name], [field]: value };
  }

  ngOnInit(): void {
    this.agentService.listAgents().subscribe(agents => {
      this.agents = agents.filter(a => a.is_active || a.id === this.data?.writer_agent_id || a.id === this.data?.analysis_agent_id);
      // A single agent is the obvious choice for a new instruction set.
      if (!this.form.value.writer_agent_id && this.agents.length === 1) {
        this.form.patchValue({ writer_agent_id: this.agents[0].id });
      }
    });
    this.credentialsService.getJiraCredentials().subscribe(credentials => {
      this.jiraCredentials = credentials;
    });

    // Switching to template mode with nothing written starts from a working template
    // rather than a blank box someone has to guess the markers for.
    this.form.get('layout_mode')?.valueChanges.subscribe(mode => {
      if (mode === 'template' && !(this.form.get('template_dita')?.value || '').trim()) {
        this.form.patchValue({ template_dita: STARTER_TEMPLATE });
      }
    });

    // An <li> outside a list is not DITA and the API refuses it, so choosing one turns a
    // list on rather than letting the person save something that cannot assemble.
    this.form.get('note_element')?.valueChanges.subscribe(value => {
      if (value === 'li' && this.form.get('notes_wrapper')?.value === 'none') {
        this.form.patchValue({ notes_wrapper: 'ul' });
      }
    });
    this.form.get('notes_wrapper')?.valueChanges.subscribe(value => {
      if (value === 'none' && this.form.get('note_element')?.value === 'li') {
        this.form.patchValue({ note_element: 'div' });
      }
    });

    // Only the active mode's field is required, so the validators move with the switch.
    this.applyModeValidators();
    this.form.get('source_mode')?.valueChanges.subscribe(() => {
      this.applyModeValidators();
      this.loadReleases();
    });
    this.form.get('jira_project')?.valueChanges
      .pipe(debounceTime(400), distinctUntilChanged())
      .subscribe(() => this.loadReleases());
    this.loadReleases();
  }

  private applyModeValidators(): void {
    const jql = this.form.get('jql_query');
    const project = this.form.get('jira_project');
    if (this.isReleasesMode) {
      jql?.clearValidators();
      project?.setValidators(Validators.required);
    } else {
      jql?.setValidators(Validators.required);
      project?.clearValidators();
    }
    jql?.updateValueAndValidity({ emitEvent: false });
    project?.updateValueAndValidity({ emitEvent: false });
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    if (!this.form.valid) return;
    const value = { ...this.form.value };
    for (const key of ['description', 'product_name', 'relevance_guidance', 'organization_guidance', 'heretto_folder_id']) {
      if (typeof value[key] === 'string' && !value[key].trim()) value[key] = null;
    }
    value.layout = {
      mode: value.layout_mode,
      template: { dita: value.layout_mode === 'template' ? (value.template_dita || '').trim() : (value.template_dita || '') },
      agent: { guidance: (value.agent_guidance || '').trim() },
      structured: {
        group_heading: value.group_heading,
        notes_wrapper: value.notes_wrapper,
        note_element: value.note_element,
        shortdesc: value.shortdesc,
        shortdesc_text: value.shortdesc === 'text' ? (value.shortdesc_text || '').trim() : ''
      }
    };
    for (const key of ['group_heading', 'notes_wrapper', 'note_element', 'shortdesc',
                       'shortdesc_text', 'layout_mode', 'template_dita', 'agent_guidance']) {
      delete value[key];
    }

    value.layout = {
      mode: value.layout_mode,
      template: { dita: value.layout_mode === 'template' ? (value.template_dita || '').trim() : (value.template_dita || '') },
      agent: { guidance: (value.agent_guidance || '').trim() },
      structured: {
        group_heading: value.group_heading,
        notes_wrapper: value.notes_wrapper,
        note_element: value.note_element,
        shortdesc: value.shortdesc,
        shortdesc_text: value.shortdesc === 'text' ? (value.shortdesc_text || '').trim() : ''
      }
    };
    for (const key of ['group_heading', 'notes_wrapper', 'note_element', 'shortdesc',
                       'shortdesc_text', 'layout_mode', 'template_dita', 'agent_guidance']) {
      delete value[key];
    }

    if (this.isReleasesMode) {
      // The query is built per release from these two; a template would have nothing to fill.
      value.jira_project = (value.jira_project || '').trim().toUpperCase();
      value.extra_jql = (value.extra_jql || '').trim() || null;
      value.jql_query = '';
      value.variables = {};
    } else {
      value.jira_project = null;
      value.extra_jql = null;
      // Send specs only for tokens the query still contains. The server normalizes too, but
      // sending the stale ones would make the request disagree with what the editor showed.
      const names = this.variableNames;
      value.variables = Object.fromEntries(names.map(name => [name, this.variableSpecs[name]]));
    }
    this.dialogRef.close(value);
  }
}
