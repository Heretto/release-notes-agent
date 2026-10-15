import { Component, OnInit, OnDestroy, ViewChild, ElementRef, inject, ChangeDetectionStrategy } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { HopDitaContentComponent, HopDitaLinkEvent, HopConfirmDialogComponent } from '@heretto/hop-ui';
import { Subscription, interval } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import {
  JobsService, Job, ReleaseNoteItem, ReleaseNoteTopic, ChunkingStrategy, CHUNKING_STRATEGIES, ChatSendResponse,
  ReleaseNoteItemDetail, ItemStatus
} from '../../../core/services/jobs.service';
import { InstructionsService, InstructionSet } from '../../../core/services/instructions.service';
import { WorkspaceChatComponent } from './workspace-chat.component';
import { WorkspaceItemDetailComponent } from './workspace-item-detail.component';

interface ItemGroup {
  name: string;
  items: ReleaseNoteItem[];
}

type ListFilter = 'all' | 'attention' | ItemStatus;

/** Pane widths, in pixels. The middle pane takes whatever is left. */
interface PaneWidths { left: number; right: number; }

/** Where the dragged pane widths are remembered between visits. */
const PANES_KEY = 'rn-workspace-panes';

/**
 * What a pane may be dragged to. Dragging squeezes the middle pane first; once it is down to
 * MIDDLE_MIN the opposite side pane gives way instead, so a drag never collapses the topic.
 */
const PANE_LIMITS = { leftMin: 200, leftMax: 480, rightMin: 280, rightMax: 600, middleMin: 380 };

/** Each drag handle occupies a track of its own, so two of these come off the usable width. */
const HANDLE_WIDTH = 12;

@Component({
  selector: 'app-workspace',
  standalone: true,
  imports: [
    DatePipe, RouterLink, MatButtonModule, MatIconModule, MatTooltipModule, MatMenuModule,
    MatProgressSpinnerModule, MatButtonToggleModule, MatSnackBarModule, MatDialogModule,
    HopDitaContentComponent, WorkspaceChatComponent, WorkspaceItemDetailComponent
  ],
  template: `
    <div class="workspace">
      @if (loading) {
        <div class="loading"><mat-spinner></mat-spinner><p>Opening workspace…</p></div>
      }

      @if (!loading && job) {
        <header class="ws-header">
          <a mat-icon-button [routerLink]="['/releases', job.id]" matTooltip="Release details"><mat-icon>arrow_back</mat-icon></a>
          <div class="ws-title">
            <h1>{{ job.title || job.output_filename || 'Release notes' }}</h1>
            <span class="muted">
              {{ includedCount }} notes · {{ approvedCount }} approved
              @if (attentionCount) { · <span class="attention">{{ attentionCount }} need attention</span> }
              @if (job.last_run_at) { · run {{ job.run_count }} on {{ job.last_run_at | date:'short' }} }
            </span>
          </div>
          <div class="ws-actions">
            @if (busy) { <mat-spinner diameter="20"></mat-spinner> }
            <button mat-stroked-button [matMenuTriggerFor]="chunkMenu" matTooltip="How notes are split into topics">
              <mat-icon>view_agenda</mat-icon>
              {{ chunkingLabel(job.chunking_strategy) }}
            </button>
            <mat-menu #chunkMenu="matMenu">
              @for (strategy of chunkingStrategies; track strategy.value) {
                <button mat-menu-item (click)="reassemble(strategy.value)" [disabled]="strategy.value === job.chunking_strategy">
                  <mat-icon>{{ strategy.value === job.chunking_strategy ? 'check' : '' }}</mat-icon>
                  <span>{{ strategy.label }}</span>
                </button>
              }
            </mat-menu>
            <button mat-stroked-button [matMenuTriggerFor]="moreMenu"><mat-icon>more_horiz</mat-icon> More</button>
            <mat-menu #moreMenu="matMenu">
              <button mat-menu-item (click)="downloadAll()"><mat-icon>download</mat-icon><span>Download DITA ({{ topics.length }})</span></button>
              <button mat-menu-item (click)="publish()"><mat-icon>cloud_upload</mat-icon><span>Publish to Heretto</span></button>
              <button mat-menu-item (click)="rerun()"><mat-icon>replay</mat-icon><span>Rerun: check Jira for changes</span></button>
              <button mat-menu-item (click)="approveAll()"><mat-icon>done_all</mat-icon><span>Approve every note</span></button>
            </mat-menu>
          </div>
        </header>

        @if (job.status === 'running' || job.status === 'pending') {
          <div class="running-banner hop-shimmer">
            <mat-icon>sync</mat-icon>
            A run is in progress ({{ job.stage_message || job.stage }}). Editing resumes when it finishes.
          </div>
        }

        <div class="columns" #columns [style.grid-template-columns]="gridTemplate">
          <!-- Notes -->
          <aside class="notes-pane">
            <div class="pane-head">
              <mat-button-toggle-group [value]="filter" (change)="filter = $event.value" hideSingleSelectionIndicator class="filter-toggle">
                <mat-button-toggle value="all">All</mat-button-toggle>
                <mat-button-toggle value="attention" [disabled]="attentionCount === 0">
                  <mat-icon class="toggle-icon">flag</mat-icon>{{ attentionCount }}
                </mat-button-toggle>
                <mat-button-toggle value="draft">Draft</mat-button-toggle>
                <mat-button-toggle value="approved">Approved</mat-button-toggle>
              </mat-button-toggle-group>
            </div>
            <div class="notes-scroll">
              @if (visibleGroups.length === 0) {
                <p class="muted empty-note">No notes match this filter.</p>
              }
              @for (group of visibleGroups; track group.name) {
                <div class="group">
                  <div class="group-head">{{ group.name || 'Ungrouped' }} <span class="muted">{{ group.items.length }}</span></div>
                  @for (item of group.items; track item.id) {
                    <button class="note-row" [class.selected]="item.id === selectedItemId" [class.rejected]="item.status === 'rejected'"
                            (click)="selectItem(item)">
                      <span class="status-dot" [class]="'status-dot status-' + item.status" [matTooltip]="statusLabel(item.status)"></span>
                      <span class="note-main">
                        <span class="note-title">{{ item.title }}</span>
                        <span class="note-meta muted">
                          {{ item.issue_keys.join(', ') || 'no issue' }}
                          @if (item.user_edited) { · <mat-icon class="mini-icon" matTooltip="Edited by a person">edit</mat-icon> }
                          @if (item.has_notes) { · <mat-icon class="mini-icon" matTooltip="Has notes">sticky_note_2</mat-icon> }
                        </span>
                      </span>
                      @if (item.needs_attention) {
                        <mat-icon class="attention-flag" [matTooltip]="item.attention_reason || 'Needs attention'">flag</mat-icon>
                      }
                    </button>
                  }
                </div>
              }
            </div>
          </aside>

          <div class="pane-handle" role="separator" aria-orientation="vertical"
               aria-label="Resize the notes list" (pointerdown)="startResize($event, 'left')"></div>

          <!-- Topic -->
          <section class="topic-pane">
            <div class="pane-head topic-head">
              <div class="topic-tabs">
                @for (topic of topics; track topic.id) {
                  <button class="topic-tab" [class.active]="topic.id === selectedTopicId" (click)="selectTopic(topic)">
                    {{ topic.title }}
                    <span class="muted">{{ topic.item_ids.length }}</span>
                  </button>
                }
              </div>
              <span class="spacer"></span>
              <mat-button-toggle-group [value]="view" (change)="view = $event.value" hideSingleSelectionIndicator class="view-toggle">
                <mat-button-toggle value="rendered" matTooltip="Rendered"><mat-icon>article</mat-icon></mat-button-toggle>
                <mat-button-toggle value="xml" matTooltip="DITA source"><mat-icon>code</mat-icon></mat-button-toggle>
              </mat-button-toggle-group>
              @if (selectedTopic) {
                <button mat-icon-button matTooltip="Download this topic" (click)="downloadTopic(selectedTopic)"><mat-icon>download</mat-icon></button>
              }
            </div>
            <div class="topic-scroll" [class.xml-view]="view === 'xml'">
              @if (!selectedTopic) {
                <p class="muted empty-note">No topic yet. Approve or edit notes and the topic appears here.</p>
              } @else if (view === 'rendered') {
                <div class="topic-render" [attr.data-topic]="selectedTopic.slug">
                  <hop-dita-content [html]="selectedTopic.html || ''" (linkClick)="onLinkClick($event)"></hop-dita-content>
                </div>
                @if (selectedTopic.render_warnings.length) {
                  <ul class="render-warnings">
                    @for (warning of selectedTopic.render_warnings; track $index) { <li>{{ warning }}</li> }
                  </ul>
                }
              } @else {
                <div class="hop-code-panel"><pre>{{ selectedTopic.dita_content }}</pre></div>
              }
            </div>
          </section>

          <div class="pane-handle" role="separator" aria-orientation="vertical"
               aria-label="Resize the details pane" (pointerdown)="startResize($event, 'right')"></div>

          <!-- Chat / note details -->
          <aside class="side-pane">
            <div class="pane-head side-tabs">
              <button class="side-tab" [class.active]="rightPane === 'chat'" (click)="rightPane = 'chat'">
                <mat-icon>forum</mat-icon> Chat
              </button>
              <button class="side-tab" [class.active]="rightPane === 'item'" (click)="rightPane = 'item'" [disabled]="!selectedItemId">
                <mat-icon>info</mat-icon> Details
              </button>
            </div>
            <div class="side-body">
              @if (rightPane === 'item' && selectedItemId) {
                <app-workspace-item-detail [jobId]="job.id" [itemId]="selectedItemId" [groups]="groupNames" [disabled]="!editable"
                                           (updated)="onItemUpdated($event)" (closed)="rightPane = 'chat'">
                </app-workspace-item-detail>
              } @else {
                <app-workspace-chat [jobId]="job.id" [selectedItem]="selectedItem" [agentName]="instructionSet?.writer_agent_name || null"
                                    [disabled]="!editable" (changed)="onChatChanged($event)">
                </app-workspace-chat>
              }
            </div>
          </aside>
        </div>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    :host { display: block; }
    .workspace { display: flex; flex-direction: column; height: calc(100vh - 96px); min-height: 480px; }
    .loading { display: flex; flex-direction: column; align-items: center; padding: 60px; color: var(--text-secondary); }
    .ws-header { display: flex; align-items: center; gap: 12px; padding: 0 0 12px 0; }
    .ws-title { flex: 1; min-width: 0; }
    .ws-title h1 { margin: 0; font-size: 20px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .ws-actions { display: flex; align-items: center; gap: 8px; }
    .muted { color: var(--text-tertiary); font-size: 12px; }
    .attention { color: var(--color-warning-text); }
    .running-banner { display: flex; align-items: center; gap: 8px; padding: 8px 14px; margin-bottom: 10px; border-radius: 8px; background: var(--color-info-bg); color: var(--color-info-text); font-size: 13px; }
    /* Widths come from gridTemplate so the handles can drive them; see startResize(). */
    .columns { display: grid; flex: 1; min-height: 0; }
    /* Each handle is its own 12px track, matching the design; no grid gap. */
    .pane-handle { cursor: col-resize; display: flex; align-items: center; justify-content: center;
      touch-action: none; }
    .pane-handle::after { content: ''; width: 2px; height: 36px; border-radius: 1px;
      background: var(--border-default); transition: background 120ms; }
    .pane-handle:hover::after, .pane-handle.dragging::after { background: var(--color-primary); }
    @media (max-width: 1024px) { .workspace { height: auto; } .columns { grid-template-columns: 1fr; }
      .pane-handle { display: none; }
      .notes-pane, .topic-pane, .side-pane { height: 60vh; } }
    .notes-pane, .topic-pane, .side-pane { display: flex; flex-direction: column; min-height: 0; border: 1px solid var(--border-default); border-radius: 12px; background: var(--card-bg); overflow: hidden; }
    .pane-head { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-bottom: 1px solid var(--border-default); min-height: 44px; }
    .spacer { flex: 1; }
    .filter-toggle, .view-toggle { height: 32px; }
    .filter-toggle ::ng-deep .mat-button-toggle-label-content, .view-toggle ::ng-deep .mat-button-toggle-label-content { line-height: 30px; padding: 0 10px; font-size: 12px; }
    .toggle-icon { font-size: 14px; width: 14px; height: 14px; vertical-align: middle; margin-right: 2px; }
    .notes-scroll { flex: 1; overflow-y: auto; padding: 6px 0; }
    .empty-note { padding: 24px 16px; text-align: center; }
    .group-head { padding: 10px 14px 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-secondary); display: flex; justify-content: space-between; }
    .note-row { display: flex; align-items: flex-start; gap: 10px; width: 100%; text-align: left; padding: 8px 14px; border: none; border-left: 3px solid transparent; background: transparent; cursor: pointer; font: inherit; color: var(--text-primary); }
    .note-row:hover { background: var(--hover-overlay); }
    .note-row.selected { background: var(--color-accent-bg, var(--hover-overlay)); border-left-color: var(--color-accent); }
    .note-row.rejected .note-title { text-decoration: line-through; color: var(--text-tertiary); }
    .status-dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; background: var(--border-strong); }
    .status-review { background: var(--color-warning); }
    .status-approved { background: var(--color-success); }
    .status-rejected { background: var(--color-error); }
    .note-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
    .note-title { font-size: 13px; line-height: 1.3; }
    .note-meta { display: flex; align-items: center; gap: 3px; flex-wrap: wrap; }
    .mini-icon { font-size: 12px; width: 12px; height: 12px; vertical-align: middle; }
    .attention-flag { color: var(--color-warning); font-size: 18px; width: 18px; height: 18px; flex-shrink: 0; }
    .topic-tabs { display: flex; gap: 4px; overflow-x: auto; min-width: 0; }
    .topic-tab { border: 1px solid transparent; background: transparent; padding: 5px 10px; border-radius: 8px; cursor: pointer; font: inherit; font-size: 13px; color: var(--text-secondary); white-space: nowrap; display: inline-flex; gap: 6px; align-items: center; }
    .topic-tab.active { background: var(--bg-secondary); color: var(--text-primary); border-color: var(--border-default); font-weight: 500; }
    .topic-scroll { flex: 1; overflow-y: auto; padding: 20px 28px; }
    .topic-scroll.xml-view { padding: 12px; }
    .topic-scroll .hop-code-panel pre { white-space: pre-wrap; word-break: break-word; font-size: 12px; }
    .topic-render { max-width: 820px; }
    .render-warnings { margin-top: 16px; color: var(--color-warning-text); font-size: 12px; }
    .side-tabs { gap: 0; padding: 0; }
    .side-tab { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 12px; border: none; border-bottom: 2px solid transparent; background: transparent; cursor: pointer; font: inherit; font-size: 13px; color: var(--text-secondary); }
    .side-tab.active { color: var(--text-primary); border-bottom-color: var(--color-accent); font-weight: 500; }
    .side-tab:disabled { opacity: 0.5; cursor: default; }
    .side-tab mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .side-body { flex: 1; min-height: 0; }
  `]
})
export class WorkspaceComponent implements OnInit, OnDestroy {
  @ViewChild('columns') columnsRef?: ElementRef<HTMLElement>;
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private jobsService = inject(JobsService);
  private instructionsService = inject(InstructionsService);
  private snackBar = inject(MatSnackBar);
  private dialog = inject(MatDialog);

  job: Job | null = null;
  instructionSet: InstructionSet | null = null;
  items: ReleaseNoteItem[] = [];
  topics: ReleaseNoteTopic[] = [];
  loading = true;
  busy = false;
  filter: ListFilter = 'all';
  view: 'rendered' | 'xml' = 'rendered';
  rightPane: 'chat' | 'item' = 'chat';
  selectedItemId: string | null = null;
  selectedTopicId: string | null = null;
  chunkingStrategies = CHUNKING_STRATEGIES;

  private jobPoll?: Subscription;

  // ── Resizable panes ───────────────────────────────────────────────────────────────

  panes: PaneWidths = { left: 260, right: 340 };
  private dragging: { side: 'left' | 'right'; startX: number; startLeft: number; startRight: number } | null = null;
  private stopDrag: (() => void) | null = null;

  get gridTemplate(): string {
    return `${this.panes.left}px ${HANDLE_WIDTH}px minmax(0, 1fr) ${HANDLE_WIDTH}px ${this.panes.right}px`;
  }

  private restorePanes(): void {
    try {
      const raw = localStorage.getItem(PANES_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw) as Partial<PaneWidths>;
      if (typeof saved.left === 'number' && typeof saved.right === 'number') {
        this.panes = {
          left: this.clamp(saved.left, PANE_LIMITS.leftMin, PANE_LIMITS.leftMax),
          right: this.clamp(saved.right, PANE_LIMITS.rightMin, PANE_LIMITS.rightMax),
        };
      }
    } catch {
      // A private window, cleared site data, or storage the browser refuses: keep defaults.
    }
  }

  private persistPanes(): void {
    try {
      localStorage.setItem(PANES_KEY, JSON.stringify(this.panes));
    } catch {
      // Not worth telling anyone about — the layout simply will not be remembered.
    }
  }

  private clamp(value: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, value));
  }

  startResize(event: PointerEvent, side: 'left' | 'right'): void {
    event.preventDefault();
    const handle = event.target as HTMLElement;
    handle.classList.add('dragging');
    this.dragging = { side, startX: event.clientX, startLeft: this.panes.left, startRight: this.panes.right };

    const move = (e: PointerEvent) => this.onResizeMove(e);
    const up = () => {
      handle.classList.remove('dragging');
      this.dragging = null;
      this.persistPanes();
      this.stopDrag?.();
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up, { once: true });
    this.stopDrag = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      this.stopDrag = null;
    };
  }

  private onResizeMove(event: PointerEvent): void {
    const drag = this.dragging;
    const container = this.columnsRef?.nativeElement;
    if (!drag || !container) return;

    const total = container.clientWidth - HANDLE_WIDTH * 2;
    const delta = event.clientX - drag.startX;

    if (drag.side === 'left') {
      let left = this.clamp(drag.startLeft + delta, PANE_LIMITS.leftMin, PANE_LIMITS.leftMax);
      let right = drag.startRight;
      // Squeeze the middle first; when it runs out, take it from the right pane.
      const overflow = PANE_LIMITS.middleMin - (total - left - right);
      if (overflow > 0) {
        right = Math.max(PANE_LIMITS.rightMin, right - overflow);
        left = Math.min(left, total - right - PANE_LIMITS.middleMin);
      }
      this.panes = { left: Math.round(left), right: Math.round(right) };
    } else {
      // The right handle grows the pane as the pointer moves left, hence the negated delta.
      let right = this.clamp(drag.startRight - delta, PANE_LIMITS.rightMin, PANE_LIMITS.rightMax);
      let left = drag.startLeft;
      const overflow = PANE_LIMITS.middleMin - (total - left - right);
      if (overflow > 0) {
        left = Math.max(PANE_LIMITS.leftMin, left - overflow);
        right = Math.min(right, total - left - PANE_LIMITS.middleMin);
      }
      this.panes = { left: Math.round(left), right: Math.round(right) };
    }
  }

  ngOnInit(): void {
    this.restorePanes();
    const jobId = this.route.snapshot.paramMap.get('id');
    if (!jobId) { this.router.navigate(['/releases']); return; }
    this.jobsService.getJob(jobId).subscribe({
      next: (job) => {
        this.job = job;
        if (job.instruction_set_id) {
          this.instructionsService.getInstructionSet(job.instruction_set_id).subscribe({ next: s => this.instructionSet = s, error: () => {} });
        }
        this.reload(true);
        this.watchRuns();
      },
      error: () => this.router.navigate(['/releases'])
    });
  }

  ngOnDestroy(): void {
    this.jobPoll?.unsubscribe();
    // A drag in progress keeps window listeners alive past this component otherwise.
    this.stopDrag?.();
  }

  // ── Derived state ────────────────────────────────────────────────────────

  get editable(): boolean {
    return !!this.job && this.job.status !== 'running' && this.job.status !== 'pending';
  }

  get selectedItem(): ReleaseNoteItem | null {
    return this.items.find(i => i.id === this.selectedItemId) || null;
  }

  get selectedTopic(): ReleaseNoteTopic | null {
    return this.topics.find(t => t.id === this.selectedTopicId) || this.topics[0] || null;
  }

  get includedCount(): number { return this.items.filter(i => i.status !== 'rejected').length; }
  get approvedCount(): number { return this.items.filter(i => i.status === 'approved').length; }
  get attentionCount(): number { return this.items.filter(i => i.needs_attention).length; }

  get groupNames(): string[] {
    const names: string[] = [];
    for (const item of this.items) {
      const name = item.group_name || '';
      if (name && !names.includes(name)) names.push(name);
    }
    return names;
  }

  get visibleGroups(): ItemGroup[] {
    const visible = this.items.filter(item => {
      if (this.filter === 'all') return true;
      if (this.filter === 'attention') return item.needs_attention;
      return item.status === this.filter;
    });
    const groups: ItemGroup[] = [];
    for (const item of visible) {
      const name = item.group_name || '';
      let group = groups.find(g => g.name === name);
      if (!group) { group = { name, items: [] }; groups.push(group); }
      group.items.push(item);
    }
    return groups;
  }

  chunkingLabel(strategy: ChunkingStrategy): string {
    return CHUNKING_STRATEGIES.find(s => s.value === strategy)?.label || strategy;
  }

  statusLabel(status: ItemStatus): string {
    return { draft: 'Draft', review: 'In review', approved: 'Approved', rejected: 'Rejected' }[status];
  }

  // ── Loading ──────────────────────────────────────────────────────────────

  reload(initial = false): void {
    if (!this.job) return;
    const jobId = this.job.id;
    this.busy = true;
    this.jobsService.getItems(jobId).subscribe({ next: items => this.items = items });
    this.jobsService.getTopics(jobId).subscribe({
      next: (topics) => {
        this.topics = topics;
        if (!this.selectedTopicId || !topics.some(t => t.id === this.selectedTopicId)) {
          this.selectedTopicId = topics[0]?.id || null;
        }
        this.busy = false;
        this.loading = false;
        if (!initial) this.highlightSelected();
      },
      error: () => { this.busy = false; this.loading = false; }
    });
    this.jobsService.getJob(jobId).subscribe({ next: job => this.job = job });
  }

  private watchRuns(): void {
    // While a run is in progress the workspace is read-only; refresh when it finishes.
    this.jobPoll = interval(5000).pipe(switchMap(() => this.jobsService.getJob(this.job!.id))).subscribe({
      next: (job) => {
        const wasRunning = this.job?.status === 'running' || this.job?.status === 'pending';
        this.job = job;
        const running = job.status === 'running' || job.status === 'pending';
        if (wasRunning && !running) this.reload();
      }
    });
  }

  // ── Selection ────────────────────────────────────────────────────────────

  selectItem(item: ReleaseNoteItem): void {
    this.selectedItemId = item.id;
    this.rightPane = 'item';
    if (item.topic_id && item.topic_id !== this.selectedTopicId) {
      this.selectedTopicId = item.topic_id;
    }
    this.view = 'rendered';
    this.highlightSelected();
  }

  selectTopic(topic: ReleaseNoteTopic): void {
    this.selectedTopicId = topic.id;
  }

  private highlightSelected(): void {
    setTimeout(() => {
      document.querySelectorAll('.topic-render .rn-selected').forEach(el => el.classList.remove('rn-selected'));
      const item = this.selectedItem;
      const topic = this.selectedTopic;
      if (!item || !topic) return;
      const target = document.getElementById(`${topic.slug}__${item.fragment_id}`);
      if (target) {
        target.classList.add('rn-selected');
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 60);
  }

  onLinkClick(event: HopDitaLinkEvent): void {
    if (event.external) {
      event.event.preventDefault();
      window.open(event.href, '_blank', 'noopener');
    }
  }

  // ── Changes from the panels ──────────────────────────────────────────────

  onItemUpdated(detail: ReleaseNoteItemDetail): void {
    this.items = this.items.map(i => i.id === detail.id ? { ...i, ...detail } : i);
    this.reload();
  }

  onChatChanged(response: ChatSendResponse): void {
    this.reload();
    if (response.changed_item_ids.length === 1 && !this.selectedItemId) {
      this.selectedItemId = response.changed_item_ids[0];
    }
  }

  // ── Actions ──────────────────────────────────────────────────────────────

  reassemble(strategy: ChunkingStrategy): void {
    if (!this.job) return;
    this.busy = true;
    this.jobsService.reassembleTopics(this.job.id, strategy).subscribe({
      next: (topics) => {
        this.topics = topics;
        this.selectedTopicId = topics[0]?.id || null;
        this.job = { ...this.job!, chunking_strategy: strategy };
        this.busy = false;
        this.reload();
        this.snackBar.open(`Topics reorganized: ${this.chunkingLabel(strategy).toLowerCase()}`, 'Close', { duration: 3000 });
      },
      error: (error) => {
        this.busy = false;
        this.snackBar.open(error.error?.detail || 'Failed to reorganize topics', 'Close', { duration: 5000 });
      }
    });
  }

  approveAll(): void {
    if (!this.job) return;
    const pending = this.items.filter(i => i.status !== 'approved' && i.status !== 'rejected');
    if (pending.length === 0) { this.snackBar.open('Every note is already approved', 'Close', { duration: 2000 }); return; }
    const ref = this.dialog.open(HopConfirmDialogComponent, {
      data: { title: 'Approve every note', message: `Mark ${pending.length} note(s) as approved?`, confirmText: 'Approve' }
    });
    ref.afterClosed().subscribe(confirmed => {
      if (!confirmed) return;
      this.busy = true;
      let remaining = pending.length;
      for (const item of pending) {
        this.jobsService.updateItem(this.job!.id, item.id, { status: 'approved' }).subscribe({
          next: () => { if (--remaining === 0) this.reload(); },
          error: () => { if (--remaining === 0) this.reload(); }
        });
      }
    });
  }

  downloadTopic(topic: ReleaseNoteTopic): void {
    if (!this.job) return;
    this.jobsService.downloadTopic(this.job.id, topic.id).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = topic.filename;
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: () => this.snackBar.open('Failed to download', 'Close', { duration: 3000 })
    });
  }

  downloadAll(): void {
    for (const topic of this.topics) this.downloadTopic(topic);
  }

  publish(): void {
    if (!this.job) return;
    const ref = this.dialog.open(HopConfirmDialogComponent, {
      data: {
        title: 'Publish to Heretto',
        message: `Create or update ${this.topics.length} topic(s) in Heretto with the current release notes?`,
        confirmText: 'Publish'
      }
    });
    ref.afterClosed().subscribe(confirmed => {
      if (!confirmed) return;
      this.busy = true;
      this.jobsService.publish(this.job!.id).subscribe({
        next: (results) => {
          this.busy = false;
          const failed = results.filter(r => !r.success);
          this.snackBar.open(
            failed.length ? `Published ${results.length - failed.length} of ${results.length}: ${failed[0].message}` : `Published ${results.length} topic(s)`,
            'Close', { duration: 6000 }
          );
          this.reload();
        },
        error: (error) => {
          this.busy = false;
          this.snackBar.open(error.error?.detail || 'Publishing failed', 'Close', { duration: 6000 });
        }
      });
    });
  }

  rerun(): void {
    if (!this.job) return;
    const ref = this.dialog.open(HopConfirmDialogComponent, {
      data: {
        title: 'Rerun this release',
        message: 'Check Jira again. Unchanged issues keep their notes; changed issues are recorded in each note\'s history (notes you edited are flagged, untouched ones are rewritten); new issues get new notes.',
        confirmText: 'Rerun'
      }
    });
    ref.afterClosed().subscribe(confirmed => {
      if (!confirmed) return;
      this.jobsService.rerunJob(this.job!.id).subscribe({
        next: (job) => { this.job = job; this.router.navigate(['/releases', job.id]); },
        error: (error) => this.snackBar.open(error.error?.detail || 'Failed to rerun', 'Close', { duration: 5000 })
      });
    });
  }
}
