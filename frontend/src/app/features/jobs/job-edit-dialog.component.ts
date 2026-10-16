import { Component, Inject, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { InstructionSet, InstructionsService, JiraRelease } from '../../core/services/instructions.service';
import { CHUNKING_STRATEGIES, Job, JobUpdate } from '../../core/services/jobs.service';
import { JqlPart, jqlParts, missingValues, variableNames } from '../../core/jql-variables';

export interface JobEditDialogData {
  job: Job;
  instructionSet: InstructionSet | null;
}

/** The release's own copy of a `{name}` from the instruction set's template. */
interface EditVariable {
  name: string;
  token: string;
  label: string;
  hint: string;
}

const FIRST_RELEASES = 5;
const MORE_RELEASES = 10;

/** The key a releases-mode run records its chosen release under. Matches the backend. */
const RELEASE_VARIABLE = 'fixVersion';

@Component({
  selector: 'app-job-edit-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatIconModule, MatSelectModule, MatSlideToggleModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon>tune</mat-icon>
      Edit release
    </h2>

    <mat-dialog-content class="edit-content">
      <p class="intro">
        Changes apply to the next run. The instruction set itself — the agents, the guidance
        and the query template — is edited on the Instructions page and is always read fresh
        when a release runs.
      </p>

      <form [formGroup]="form">
        <mat-form-field appearance="outline" class="full-width" subscriptSizing="dynamic">
          <mat-label>Release title</mat-label>
          <input matInput formControlName="title" placeholder="e.g. Heretto 2026.10">
          <mat-hint>Used as the topic title</mat-hint>
        </mat-form-field>

        <div class="two-up">
          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Output filename</mat-label>
            <input matInput class="mono" formControlName="output_filename" required>
            @if (form.get('output_filename')?.hasError('required')) {
              <mat-error>An output filename is required</mat-error>
            }
          </mat-form-field>

          <mat-form-field appearance="outline" subscriptSizing="dynamic">
            <mat-label>Maximum issues to read</mat-label>
            <input matInput formControlName="max_tickets" type="number" min="1" max="500"
                   placeholder="Default 100">
          </mat-form-field>
        </div>

        <mat-form-field appearance="outline" class="full-width" subscriptSizing="dynamic">
          <mat-label>Topics</mat-label>
          <mat-select formControlName="chunking_strategy">
            @for (strategy of chunkingStrategies; track strategy.value) {
              <mat-option [value]="strategy.value">{{ strategy.label }} — {{ strategy.hint }}</mat-option>
            }
          </mat-select>
          <mat-hint>Changing this reassembles the existing notes straight away</mat-hint>
        </mat-form-field>

        @if (isReleasesMode) {
          <div class="card">
            <div class="card-head">
              <span class="card-title">Jira release</span>
              <span class="muted">{{ releasesStatus }}</span>
            </div>
            @for (release of releases; track release.name) {
              <button type="button" class="release-row" [class.chosen]="release.name === chosenRelease"
                      (click)="chosenRelease = release.name">
                <span class="radio" [class.on]="release.name === chosenRelease"></span>
                <span class="release-name">{{ release.name }}</span>
                <span class="release-count">{{ release.issue_count }} issues</span>
              </button>
            }
            @if (releasesHasMore) {
              <button type="button" class="load-more" (click)="loadMoreReleases()" [disabled]="loadingReleases">
                {{ loadingReleases ? 'Loading…' : 'Load ' + nextBatchSize + ' more' }}
              </button>
            }
          </div>
        } @else if (editVariables.length) {
          <div class="card">
            <span class="card-title">Query variables</span>
            @for (variable of editVariables; track variable.name) {
              <mat-form-field appearance="outline" class="full-width" subscriptSizing="dynamic">
                <mat-label>{{ variable.label }}</mat-label>
                <input matInput class="mono" [value]="values[variable.name] || ''"
                       (input)="setValue(variable.name, $any($event.target).value)" placeholder="Required">
                <mat-hint>{{ variable.hint || variable.token }}</mat-hint>
              </mat-form-field>
            }
          </div>
        }

        <div class="preview-block">
          <span class="preview-label">Query the next run will use</span>
          <div class="query-preview">
            @if (!canRebuildQuery) {
              <span>{{ data.job.jql_query }}</span>
            } @else if (isReleasesMode) {
              <span>{{ releaseQueryPreview }}</span>
            } @else {
              @for (part of previewParts; track $index) {
                @if (part.isVar) { <span class="chip-filled">{{ part.text }}</span> }
                @else if (part.isEmpty) { <span class="chip-missing">{{ part.text }}</span> }
                @else { <span>{{ part.text }}</span> }
              }
            }
          </div>
          @if (!canRebuildQuery) {
            <p class="note muted">
              This release was started with a query of its own, so it is not rebuilt from the
              instruction set.
            </p>
          } @else if (blockedReason) {
            <p class="note error">{{ blockedReason }}</p>
          }
        </div>

        <div class="publish-row">
          <mat-slide-toggle formControlName="publish_to_heretto">Publish to Heretto when a run finishes</mat-slide-toggle>
        </div>
        @if (form.value.publish_to_heretto) {
          <mat-form-field appearance="outline" class="full-width" subscriptSizing="dynamic">
            <mat-label>Heretto folder</mat-label>
            <input matInput class="mono" formControlName="heretto_folder_id" placeholder="Folder id">
          </mat-form-field>
        }
      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
      <button mat-raised-button color="primary" [disabled]="blocked" (click)="onSave()">Save changes</button>
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    mat-dialog-content.edit-content { min-width: 520px; max-width: 620px; padding-bottom: 20px; }
    h2 { display: flex; align-items: center; gap: 10px; }
    .intro { color: var(--text-secondary); font-size: 13px; margin: 0 0 16px; line-height: 1.55; }
    .full-width { width: 100%; }
    form > * { margin-bottom: 16px; }
    .two-up { display: grid; grid-template-columns: 1.6fr 1fr; gap: 12px; align-items: start; }
    .two-up mat-form-field { width: 100%; }
    .mono { font-family: var(--font-mono); font-size: 13px; }
    .card { border: 1px solid var(--border-default); border-radius: 8px; background: var(--bg-secondary);
      padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; }
    .card-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
    .card-title { font-size: 13px; font-weight: 600; }
    .muted { font-size: 12px; color: var(--text-tertiary); }
    .release-row { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left; padding: 8px 12px;
      border: 1px solid var(--border-default); border-radius: 6px; background: var(--bg-primary);
      color: var(--text-primary); font: inherit; cursor: pointer; }
    .release-row.chosen { border-color: var(--color-primary); background: var(--color-primary-bg); }
    .radio { width: 14px; height: 14px; border-radius: 50%; border: 1px solid var(--border-default);
      background: var(--bg-primary); flex-shrink: 0; }
    .radio.on { border-color: var(--color-primary); background: var(--color-primary); box-shadow: inset 0 0 0 3px var(--bg-primary); }
    .release-name { flex: 1; font-family: var(--font-mono); font-size: 13px; font-weight: 600; }
    .release-count { font-size: 12px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
    .load-more { align-self: flex-end; background: none; border: none; padding: 2px; cursor: pointer;
      font: inherit; font-size: 13px; font-weight: 500; color: var(--color-primary); }
    .preview-label { display: block; font-size: 12px; font-weight: 500; color: var(--text-secondary); margin-bottom: 4px; }
    .query-preview { background: var(--bg-secondary); border: 1px solid var(--border-default); border-radius: 6px;
      padding: 10px 12px; font-family: var(--font-mono); font-size: 12px; line-height: 1.6; word-break: break-word; }
    .chip-filled { display: inline-block; padding: 0 5px; border-radius: 4px; background: var(--color-primary-bg); color: var(--color-primary-text); font-weight: 600; }
    .chip-missing { display: inline-block; padding: 0 5px; border-radius: 4px; background: var(--color-error-bg); color: var(--color-error-text); font-weight: 600; }
    .note { font-size: 12px; margin: 6px 0 0; line-height: 1.5; }
    .note.error { color: var(--color-error-text); }
    .publish-row { display: flex; align-items: center; }
    mat-dialog-actions { padding: 16px 24px; border-top: 1px solid var(--border-default); }
  `]
})
export class JobEditDialogComponent implements OnInit {
  form: FormGroup;
  chunkingStrategies = CHUNKING_STRATEGIES;

  values: Record<string, string> = {};
  chosenRelease = '';
  releases: JiraRelease[] = [];
  releasesStatus = '';
  releasesHasMore = false;
  loadingReleases = false;
  private releasesTotal = 0;
  private releasesNextStart = 0;

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<JobEditDialogComponent>,
    private instructionsService: InstructionsService,
    @Inject(MAT_DIALOG_DATA) public data: JobEditDialogData
  ) {
    const job = data.job;
    this.values = { ...(job.variables || {}) };
    this.chosenRelease = this.values[RELEASE_VARIABLE] || '';

    this.form = this.fb.group({
      title: [job.title || ''],
      output_filename: [job.output_filename || '', Validators.required],
      max_tickets: [job.max_tickets ?? null, [Validators.min(1), Validators.max(500)]],
      chunking_strategy: [job.chunking_strategy || 'single'],
      publish_to_heretto: [!!job.auto_publish],
      heretto_folder_id: [job.heretto_folder_id || '']
    });
  }

  ngOnInit(): void {
    if (this.isReleasesMode && this.canRebuildQuery) this.fetchReleases(FIRST_RELEASES);
  }

  /** A release started with its own query has no template to re-resolve against. */
  get canRebuildQuery(): boolean {
    return this.data.job.uses_instruction_query !== false && !!this.data.instructionSet;
  }

  get isReleasesMode(): boolean {
    return this.data.instructionSet?.source_mode === 'releases';
  }

  get editVariables(): EditVariable[] {
    const set = this.data.instructionSet;
    if (!set || !this.canRebuildQuery || this.isReleasesMode) return [];
    return variableNames(set.jql_query || '').map(name => {
      const spec = set.variables?.[name];
      return { name, token: `{${name}}`, label: spec?.label || name, hint: spec?.hint || '' };
    });
  }

  get previewParts(): JqlPart[] {
    return jqlParts(this.data.instructionSet?.jql_query || '', this.values);
  }

  get releaseQueryPreview(): string {
    const set = this.data.instructionSet;
    const project = (set?.jira_project || '').trim().toUpperCase();
    const extra = (set?.extra_jql || '').trim();
    if (!this.chosenRelease) return 'Choose a release to see the query it will run.';
    return `project = ${project} AND fixVersion = "${this.chosenRelease}"`
      + (extra ? ` AND (${extra})` : '') + ' ORDER BY created ASC';
  }

  get blockedReason(): string {
    if (!this.canRebuildQuery) return '';
    if (this.isReleasesMode) return this.chosenRelease ? '' : 'Choose a release.';
    const missing = missingValues(this.data.instructionSet?.jql_query || '', this.values);
    return missing.length
      ? `Fill in every variable: ${missing.join(', ')}`
      : '';
  }

  get blocked(): boolean {
    return !this.form.valid || !!this.blockedReason;
  }

  get nextBatchSize(): number {
    return Math.min(MORE_RELEASES, Math.max(this.releasesTotal - this.releases.length, 1));
  }

  setValue(name: string, value: string): void {
    this.values = { ...this.values, [name]: value };
  }

  loadMoreReleases(): void {
    if (!this.loadingReleases) this.fetchReleases(MORE_RELEASES);
  }

  private fetchReleases(count: number): void {
    const setId = this.data.instructionSet?.id;
    if (!setId) return;
    this.loadingReleases = true;
    if (!this.releases.length) this.releasesStatus = 'Loading…';
    this.instructionsService.listReleases(setId, this.releasesNextStart, count).subscribe({
      next: result => {
        this.loadingReleases = false;
        this.releases = [...this.releases, ...result.releases];
        this.releasesTotal = result.total;
        this.releasesNextStart = result.next_start;
        this.releasesHasMore = result.has_more;
        this.releasesStatus = `${this.releases.length} of ${result.total} in ${result.project}`;
      },
      error: error => {
        this.loadingReleases = false;
        this.releasesHasMore = false;
        this.releasesStatus = error.error?.detail || 'Could not read releases from Jira';
      }
    });
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    if (this.blocked) return;
    const value = this.form.value;
    const update: JobUpdate = {
      title: (value.title || '').trim() || null,
      output_filename: value.output_filename.trim(),
      max_tickets: value.max_tickets || null,
      chunking_strategy: value.chunking_strategy,
      publish_to_heretto: !!value.publish_to_heretto,
      heretto_folder_id: value.publish_to_heretto ? (value.heretto_folder_id || '').trim() || null : null
    };
    // Only send the query inputs when there is a template to resolve them against.
    if (this.canRebuildQuery) {
      if (this.isReleasesMode) update.release = this.chosenRelease;
      else update.variables = this.values;
    }
    this.dialogRef.close(update);
  }
}
