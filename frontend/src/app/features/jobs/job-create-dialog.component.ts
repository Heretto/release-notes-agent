import { Component, Inject, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { InstructionSet, InstructionsService, JiraRelease } from '../../core/services/instructions.service';
import { CHUNKING_STRATEGIES, JobCreate } from '../../core/services/jobs.service';
import { JqlPart, defaultsOf, jqlParts, missingValues, variableNames } from '../../core/jql-variables';

export interface JobCreateDialogData {
  instructionSets: InstructionSet[];
  selectedId?: string;
}

/** The picker opens on the most recent few; everything older is a press away. */
const FIRST_RELEASES = 5;
const MORE_RELEASES = 10;

/** One `{name}` the chosen instruction set's query needs a value for. */
interface StartVariable {
  name: string;
  token: string;
  label: string;
  hint: string;
}

@Component({
  selector: 'app-job-create-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatSelectModule
  ],
  template: `
    <h2 mat-dialog-title>
      <mat-icon>rocket_launch</mat-icon>
      Start a release
    </h2>

    <mat-dialog-content>
      <p class="intro">
        The agents read the issues, decide which ones matter, and draft a release note for each.
        You then finish the notes with the agent in the workspace.
      </p>
      <form [formGroup]="form">
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Instruction set</mat-label>
          <mat-select formControlName="instruction_set_id" required>
            @for (ins of instructionSets; track ins.id) {
              <mat-option [value]="ins.id" [disabled]="!ins.writer_agent_id">
                {{ ins.name }}@if (ins.is_default) { (default) }@if (!ins.writer_agent_id) { — no writer agent }
              </mat-option>
            }
          </mat-select>
        </mat-form-field>

        @if (selectedInstructionSet) {
          <p class="agents-line">
            <mat-icon>smart_toy</mat-icon>
            Writer: {{ selectedInstructionSet.writer_agent_name || '—' }}
            · Analysis: {{ selectedInstructionSet.analysis_agent_name || 'same as writer' }}
          </p>
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Release title</mat-label>
          <input matInput [value]="title" (input)="onTitle($any($event.target).value)"
                 placeholder="e.g. Heretto 2026.10">
          <mat-hint>Used as the topic title. Built from the instruction set and the values below until you change it.</mat-hint>
        </mat-form-field>

        <div class="two-up">
          <mat-form-field appearance="outline">
            <mat-label>Output filename</mat-label>
            <input matInput class="mono" [value]="filename" (input)="onFilename($any($event.target).value)"
                   placeholder="release-notes.dita">
            <mat-hint>Topic filename in Heretto and in downloads</mat-hint>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Maximum issues to read</mat-label>
            <input matInput formControlName="max_tickets" type="number" min="1" max="500"
                   placeholder="Default 100">
            <mat-hint>Stops after this many from the query</mat-hint>
          </mat-form-field>
        </div>

        @if (isReleasesMode) {
          <div class="vars-card releases-card">
            <div class="vars-head">
              <span class="vars-title">Jira release</span>
              <span class="muted">{{ releasesStatus }}</span>
            </div>
            @for (release of releases; track release.name) {
              <button type="button" class="release-row" [class.chosen]="release.name === chosenRelease"
                      (click)="chooseRelease(release)">
                <span class="radio" [class.on]="release.name === chosenRelease"></span>
                <span class="release-name">{{ release.name }}</span>
                <span class="release-chip" [class.released]="release.released">
                  {{ release.released ? 'Released' : 'Unreleased' }}
                </span>
                <span class="release-date">{{ releaseDateText(release) }}</span>
                <span class="release-count">{{ release.issue_count }} issues</span>
              </button>
            }
            @if (!releases.length) {
              <p class="muted no-releases">{{ releasesStatus }}</p>
            }
            @if (moreReleases) {
              <button type="button" class="load-more" (click)="loadMoreReleases()" [disabled]="loadingReleases">
                {{ loadingReleases ? 'Loading…' : 'Load ' + nextBatchSize + ' more' }}
              </button>
            }
          </div>
        }

        @if (startVariables.length) {
          <div class="vars-card">
            <span class="vars-title">Query variables</span>
            @for (v of startVariables; track v.name) {
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>{{ v.label }}</mat-label>
                <input matInput class="mono" [value]="values[v.name] || ''"
                       (input)="setValue(v.name, $any($event.target).value)" placeholder="Required">
                <mat-hint>{{ v.hint || v.token }}</mat-hint>
              </mat-form-field>
            }
          </div>
        }

        <div class="preview-block">
          <span class="preview-label">Query this release will run</span>
          <div class="query-preview">
            @if (isReleasesMode) {
              <span>{{ releaseQueryPreview }}</span>
            } @else {
              @for (part of previewParts; track $index) {
                @if (part.isVar) { <span class="chip-filled">{{ part.text }}</span> }
                @else if (part.isEmpty) { <span class="chip-missing">{{ part.text }}</span> }
                @else { <span>{{ part.text }}</span> }
              }
            }
          </div>
          @if (blockedReason) {
            <p class="preview-missing">{{ blockedReason }}</p>
          }
        </div>

        @if (selectedInstructionSet?.publish_to_heretto) {
          <div class="heretto-notice">
            <mat-icon>cloud_upload</mat-icon>
            <span>Topics will be published to Heretto when the run finishes</span>
          </div>
        }
      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
      <button mat-raised-button color="primary" [disabled]="blocked" (click)="onCreate()">
        <mat-icon>play_arrow</mat-icon>
        <span>Start</span>
      </button>
    </mat-dialog-actions>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    mat-dialog-content { min-width: 520px; max-width: 640px; }
    h2 { display: flex; align-items: center; gap: 10px; }
    .intro { color: var(--text-secondary); font-size: 14px; margin: 0 0 16px 0; }
    .full-width { width: 100%; }
    .two-up { display: grid; grid-template-columns: 1.6fr 1fr; gap: 12px; }
    .two-up mat-form-field { width: 100%; }
    .mono { font-family: var(--font-mono); font-size: 13px; }
    .agents-line { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); font-size: 13px; margin: 0 0 12px 0; }
    .agents-line mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .vars-card { border: 1px solid var(--border-default); border-radius: 8px; background: var(--bg-secondary);
      padding: 14px 16px 0; margin-bottom: 8px; }
    .vars-title { display: block; font-size: 13px; font-weight: 600; margin-bottom: 10px; }
    .vars-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
    .muted { font-size: 12px; color: var(--text-tertiary); }
    .releases-card { padding-bottom: 14px; display: flex; flex-direction: column; gap: 6px; }
    .no-releases { margin: 0; font-size: 13px; }
    .release-row { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left; padding: 9px 12px;
      border: 1px solid var(--border-default); border-radius: 6px; background: var(--bg-primary);
      color: var(--text-primary); font: inherit; cursor: pointer; }
    .release-row.chosen { border-color: var(--color-primary); background: var(--color-primary-bg); }
    .radio { width: 14px; height: 14px; border-radius: 50%; border: 1px solid var(--border-strong, var(--border-default));
      background: var(--bg-primary); flex-shrink: 0; }
    .radio.on { border-color: var(--color-primary); background: var(--color-primary); box-shadow: inset 0 0 0 3px var(--bg-primary); }
    .release-name { font-family: var(--font-mono); font-size: 13px; font-weight: 600; min-width: 72px; }
    .release-chip { display: inline-flex; align-items: center; font-size: 11px; font-weight: 600; padding: 4px 8px;
      border-radius: 999px; background: var(--color-info-bg, var(--bg-secondary)); color: var(--color-info-text, var(--text-secondary)); }
    .release-chip.released { background: var(--color-success-bg); color: var(--color-success-text); }
    .release-date { flex: 1; font-size: 12px; color: var(--text-tertiary); }
    .release-count { font-size: 12px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
    .load-more { align-self: flex-start; background: none; border: none; padding: 4px 2px; cursor: pointer;
      font: inherit; font-size: 13px; font-weight: 500; color: var(--color-primary); }
    .load-more:disabled { color: var(--text-tertiary); cursor: default; }
    .preview-block { margin-bottom: 8px; }
    .preview-label { display: block; font-size: 12px; font-weight: 500; color: var(--text-secondary); margin-bottom: 4px; }
    .query-preview { background: var(--bg-secondary); border: 1px solid var(--border-default); border-radius: 6px;
      padding: 10px 12px; font-family: var(--font-mono); font-size: 12px; line-height: 1.6; word-break: break-word; }
    .chip-filled { display: inline-block; padding: 0 5px; border-radius: 4px; background: var(--color-primary-bg); color: var(--color-primary-text); font-weight: 600; }
    .chip-missing { display: inline-block; padding: 0 5px; border-radius: 4px; background: var(--color-error-bg); color: var(--color-error-text); font-weight: 600; }
    .preview-missing { font-size: 12px; color: var(--color-error-text); margin: 4px 0 0; }
    .heretto-notice { display: flex; align-items: center; gap: 8px; background: var(--color-primary-bg); color: var(--color-primary-text); padding: 10px 14px; border-radius: 4px; margin-top: 8px; font-size: 14px; }
    mat-dialog-actions { padding: 20px 24px; border-top: 1px solid var(--border-default); }
  `]
})
export class JobCreateDialogComponent implements OnInit {
  form: FormGroup;
  instructionSets: InstructionSet[] = [];
  selectedInstructionSet: InstructionSet | null = null;
  chunkingStrategies = CHUNKING_STRATEGIES;

  /** Values for the chosen set's `{name}` tokens. The server does the substituting. */
  values: Record<string, string> = {};

  /** Releases mode: Jira's fix versions for the set's project, and the one chosen. */
  releases: JiraRelease[] = [];
  releasesStatus = '';
  chosenRelease = '';
  loadingReleases = false;
  /** Jira's totals for the loaded page, so the card can say "5 of 23" and offer more. */
  private releasesTotal = 0;
  private releasesNextStart = 0;
  private releasesHasMore = false;

  /**
   * Title and filename follow the instruction set and the variable values until the person
   * edits one; after that their text is kept, even if they then change a variable.
   */
  private titleTouched = false;
  private filenameTouched = false;
  private typedTitle = '';
  private typedFilename = '';

  constructor(
    private fb: FormBuilder,
    private dialogRef: MatDialogRef<JobCreateDialogComponent>,
    private instructionsService: InstructionsService,
    @Inject(MAT_DIALOG_DATA) public data: JobCreateDialogData
  ) {
    this.instructionSets = data.instructionSets;
    const preferred = this.instructionSets.find(i => i.id === data.selectedId)
      || this.instructionSets.find(i => i.is_default && i.writer_agent_id)
      || this.instructionSets.find(i => !!i.writer_agent_id)
      || this.instructionSets[0];
    this.selectedInstructionSet = preferred || null;
    this.values = defaultsOf(preferred?.variables);

    this.form = this.fb.group({
      instruction_set_id: [preferred?.id, Validators.required],
      max_tickets: [null, [Validators.min(1), Validators.max(500)]]
    });
  }

  ngOnInit() {
    this.form.get('instruction_set_id')?.valueChanges.subscribe(id => {
      const selected = this.instructionSets.find(i => i.id === id);
      if (!selected) return;
      this.selectedInstructionSet = selected;
      // A different set has different variables, so start from its defaults rather than
      // carrying over values that belonged to another query.
      this.values = defaultsOf(selected.variables);
      this.loadReleases();
    });
    this.loadReleases();
  }

  get isReleasesMode(): boolean {
    return this.selectedInstructionSet?.source_mode === 'releases';
  }

  /** The query the chosen release will run, as the server will build it. */
  get releaseQueryPreview(): string {
    const set = this.selectedInstructionSet;
    const project = (set?.jira_project || '').trim().toUpperCase();
    const extra = (set?.extra_jql || '').trim();
    if (!this.chosenRelease) return 'Choose a release to see the query it will run.';
    return `project = ${project} AND fixVersion = "${this.chosenRelease}"`
      + (extra ? ` AND (${extra})` : '') + ' ORDER BY created ASC';
  }

  get blockedReason(): string {
    if (this.isReleasesMode) return this.chosenRelease ? '' : 'Choose a release before starting.';
    return this.missing.length ? 'Fill in every variable before starting.' : '';
  }

  releaseDateText(release: JiraRelease): string {
    if (!release.date) return '';
    return `${release.released ? 'Released ' : 'Due '}${release.date}`;
  }

  chooseRelease(release: JiraRelease): void {
    this.chosenRelease = release.name;
  }

  get moreReleases(): boolean {
    return this.releasesHasMore;
  }

  /** The first page is the five most recent; each press after that fetches ten. */
  get nextBatchSize(): number {
    return Math.min(MORE_RELEASES, Math.max(this.releasesTotal - this.releases.length, 1));
  }

  /** Read live from Jira: a release list only exists there, and a stale copy would lie. */
  private loadReleases(): void {
    this.releases = [];
    this.chosenRelease = '';
    this.releasesTotal = 0;
    this.releasesNextStart = 0;
    this.releasesHasMore = false;
    const set = this.selectedInstructionSet;
    if (!set?.id || !this.isReleasesMode) {
      this.releasesStatus = '';
      return;
    }
    this.fetchReleases(set.id, FIRST_RELEASES);
  }

  loadMoreReleases(): void {
    const set = this.selectedInstructionSet;
    if (set?.id && !this.loadingReleases) this.fetchReleases(set.id, MORE_RELEASES);
  }

  private fetchReleases(instructionSetId: string, count: number): void {
    this.loadingReleases = true;
    this.releasesStatus = this.releases.length ? this.releasesStatus : 'Loading…';
    this.instructionsService.listReleases(instructionSetId, this.releasesNextStart, count).subscribe({
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
        if (!this.releases.length) this.releases = [];
        this.releasesStatus = error.error?.detail || 'Could not read releases from Jira';
      }
    });
  }

  get startVariables(): StartVariable[] {
    const set = this.selectedInstructionSet;
    if (!set || this.isReleasesMode) return [];
    return variableNames(set.jql_query || '').map(name => {
      const spec = set.variables?.[name];
      return { name, token: `{${name}}`, label: spec?.label || name, hint: spec?.hint || '' };
    });
  }

  get missing(): string[] {
    if (this.isReleasesMode) return [];
    return missingValues(this.selectedInstructionSet?.jql_query || '', this.values);
  }

  get previewParts(): JqlPart[] {
    return jqlParts(this.selectedInstructionSet?.jql_query || '', this.values);
  }

  /** The instruction set's product (or its name) plus every variable value, in query order. */
  get title(): string {
    if (this.titleTouched) return this.typedTitle;
    const set = this.selectedInstructionSet;
    if (!set) return '';
    const parts = [set.product_name || set.name];
    if (this.isReleasesMode) {
      if (this.chosenRelease) parts.push(this.chosenRelease);
    } else {
      for (const v of this.startVariables) {
        const value = (this.values[v.name] || '').trim();
        if (value) parts.push(value);
      }
    }
    return parts.filter(Boolean).join(' ');
  }

  get filename(): string {
    if (this.filenameTouched) return this.typedFilename;
    const slug = this.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    return `${slug || 'release-notes'}.dita`;
  }

  get blocked(): boolean {
    return !this.form.valid || !this.selectedInstructionSet
      || !!this.blockedReason || !this.title.trim() || !this.filename.trim();
  }

  setValue(name: string, value: string): void {
    this.values = { ...this.values, [name]: value };
  }

  onTitle(value: string): void {
    this.titleTouched = true;
    this.typedTitle = value;
  }

  onFilename(value: string): void {
    this.filenameTouched = true;
    this.typedFilename = value;
  }

  onCancel(): void {
    this.dialogRef.close();
  }

  onCreate(): void {
    if (this.blocked || !this.selectedInstructionSet) return;
    const jobData: JobCreate = {
      instruction_set_id: this.form.value.instruction_set_id,
      title: this.title.trim() || undefined,
      // No jql_query: the server builds the query — from the chosen release in releases
      // mode, otherwise from these values, each injected as a quoted literal so it cannot
      // rewrite the query.
      variables: this.isReleasesMode ? {} : this.values,
      release: this.isReleasesMode ? this.chosenRelease : undefined,
      output_filename: this.filename.trim(),
      chunking_strategy: this.selectedInstructionSet.chunking_strategy || 'single',
      max_tickets: this.form.value.max_tickets || undefined,
      publish_to_heretto: this.selectedInstructionSet.publish_to_heretto || false,
      heretto_folder_id: this.selectedInstructionSet.publish_to_heretto
        ? this.selectedInstructionSet.heretto_folder_id : undefined
    };
    this.dialogRef.close(jobData);
  }
}
