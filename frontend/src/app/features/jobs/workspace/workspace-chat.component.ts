import { Component, ElementRef, EventEmitter, Input, OnDestroy, OnInit, Output, ViewChild, inject, ChangeDetectionStrategy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HopAuthService } from '@heretto/hop-ui';
import { Subscription } from 'rxjs';
import { JobsService, ChatMessage, ChatSendResponse, ReleaseNoteItem } from '../../../core/services/jobs.service';

@Component({
  selector: 'app-workspace-chat',
  standalone: true,
  imports: [FormsModule, MatIconModule, MatProgressSpinnerModule, MatTooltipModule],
  template: `
    <div class="chat">
      <div class="chat-head">
        <span class="agent-mark"><mat-icon>auto_awesome</mat-icon></span>
        <div class="chat-head-text">
          <div class="agent-name">{{ agentName || 'Writer agent' }}</div>
          <div class="chat-subtitle">
            @if (selectedItem) {
              Talking about “{{ selectedItem.title }}”
            } @else {
              Ask for changes to any note, or select one to talk about it
            }
          </div>
        </div>
        <button class="icon-btn" matTooltip="Clear conversation" (click)="clear()" [disabled]="messages.length === 0 || sending">
          <mat-icon>delete</mat-icon>
        </button>
      </div>

      <div class="transcript" #transcript>
        @for (message of messages; track message.id) {
          <div class="turn">
            <span class="avatar" [class.user]="message.role === 'user'" [class.agent]="message.role === 'assistant'">
              {{ message.role === 'user' ? userInitials : '✦' }}
            </span>
            <div class="turn-body">
              <div class="turn-name">{{ message.role === 'user' ? 'You' : (agentName || 'Writer agent') }}</div>
              <div class="turn-text">{{ message.content }}</div>
              @for (action of message.actions || []; track $index) {
                <div class="action" [class.failed]="!action.ok">
                  <mat-icon>{{ action.ok ? 'check_circle' : 'error' }}</mat-icon>
                  <span>{{ action.description || action.result }}</span>
                </div>
              }
            </div>
          </div>
        }
        @if (messages.length === 0 && !sending) {
          <p class="empty">
            Try: “Make this note shorter”, “Approve this note”, “Split the notes into one topic per group”,
            or “What changed in {{ exampleIssueKey }}?”
          </p>
        }
        @if (sending) {
          <div class="working"><mat-spinner diameter="14"></mat-spinner> Working…</div>
        }
      </div>

      <form class="composer" (ngSubmit)="send()">
        <div class="composer-box">
          <textarea [(ngModel)]="draft" name="draft" rows="2" placeholder="Ask the agent to change the release notes…"
                    (keydown)="onKeydown($event)" [disabled]="sending || disabled"></textarea>
          <div class="composer-row">
            <span class="context-chip" [matTooltip]="selectedItem ? 'The agent sees the selected note as “this note”' : 'No note selected; the agent works on all notes'">
              {{ selectedItem ? 'this note' : 'all notes' }}
            </span>
            <span class="spacer"></span>
            <button class="send-btn" type="submit" [disabled]="!draft.trim() || sending || disabled" matTooltip="Send (Enter)" aria-label="Send">
              <mat-icon>arrow_upward</mat-icon>
            </button>
          </div>
        </div>
      </form>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    :host { display: block; height: 100%; min-height: 0; }
    .chat { display: flex; flex-direction: column; height: 100%; min-height: 0; font-size: 14px; }

    .chat-head { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--border-light); }
    .agent-mark { width: 28px; height: 28px; border-radius: 6px; background: var(--color-accent-bg); color: var(--color-accent-text); display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
    .agent-mark mat-icon { font-size: 16px; width: 16px; height: 16px; }
    .chat-head-text { flex: 1; min-width: 0; }
    .agent-name { font-size: 14px; font-weight: 600; line-height: 1.2; }
    .chat-subtitle { font-size: 11px; color: var(--text-tertiary); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .icon-btn { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; padding: 0; border: none; border-radius: 6px; background: transparent; color: var(--text-secondary); cursor: pointer; flex-shrink: 0; }
    .icon-btn:hover { background: var(--bg-secondary); color: var(--text-primary); }
    .icon-btn:disabled { opacity: 0.4; cursor: default; }
    .icon-btn mat-icon { font-size: 16px; width: 16px; height: 16px; }

    .transcript { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 14px; min-height: 0; }
    .turn { display: flex; gap: 10px; }
    .avatar { width: 24px; height: 24px; border-radius: 6px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 600; line-height: 1; }
    .avatar.user { background: var(--color-primary-bg); color: var(--color-primary-text); }
    .avatar.agent { background: var(--color-accent-bg); color: var(--color-accent-text); }
    .turn-body { flex: 1; min-width: 0; }
    .turn-name { font-size: 12px; font-weight: 600; line-height: 1.2; color: var(--text-primary); }
    .turn-text { font-size: 13px; line-height: 1.5; color: var(--text-secondary); margin-top: 4px; white-space: pre-wrap; word-break: break-word; }
    .action { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-secondary); margin-top: 6px; }
    .action mat-icon { font-size: 14px; width: 14px; height: 14px; color: var(--color-success); }
    .action.failed mat-icon { color: var(--color-error); }
    .empty { color: var(--text-tertiary); text-align: center; padding: 28px 12px; font-size: 13px; margin: 0; }
    .working { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 13px; padding-left: 34px; }

    .composer { padding: 12px; border-top: 1px solid var(--border-light); }
    .composer-box { border: 1px solid var(--border-default); border-radius: 8px; padding: 8px 10px; display: flex; flex-direction: column; gap: 8px; background: var(--bg-primary); }
    .composer-box:focus-within { border-color: var(--border-focus); }
    .composer-box textarea { border: none; outline: none; resize: none; font: inherit; font-size: 13px; line-height: 1.5; color: var(--text-primary); width: 100%; background: transparent; padding: 0; }
    .composer-row { display: flex; align-items: center; gap: 6px; }
    .context-chip { font-size: 11px; font-weight: 500; line-height: 1; padding: 4px 8px; border-radius: 4px; background: var(--color-primary-bg); color: var(--color-primary-text); }
    .spacer { flex: 1; }
    .send-btn { width: 28px; height: 28px; border-radius: 6px; background: var(--color-primary); color: var(--text-inverse); border: none; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; padding: 0; }
    .send-btn:hover { background: var(--color-primary-hover); }
    .send-btn:disabled { opacity: 0.4; cursor: default; }
    .send-btn mat-icon { font-size: 14px; width: 14px; height: 14px; }
  `]
})
export class WorkspaceChatComponent implements OnInit, OnDestroy {
  private jobsService = inject(JobsService);
  private auth = inject(HopAuthService);
  private snackBar = inject(MatSnackBar);

  @Input({ required: true }) jobId!: string;
  @Input() selectedItem: ReleaseNoteItem | null = null;
  @Input() agentName: string | null = null;
  @Input() disabled = false;
  /** The agent changed notes and/or topics; the workspace reloads them. */
  @Output() changed = new EventEmitter<ChatSendResponse>();

  @ViewChild('transcript') transcript?: ElementRef<HTMLDivElement>;

  messages: ChatMessage[] = [];
  draft = '';
  sending = false;
  userInitials = 'Y';

  private userSub?: Subscription;

  get exampleIssueKey(): string {
    return this.selectedItem?.issue_keys[0] || 'PROJ-123';
  }

  ngOnInit(): void {
    this.userSub = this.auth.currentUser$.subscribe(user => {
      // hop-ui's user carries an email, not a name: the local part's initial stands in.
      const local = (user?.email || '').split('@')[0];
      this.userInitials = local ? local[0].toUpperCase() : 'Y';
    });
    this.jobsService.getChat(this.jobId).subscribe({
      next: (messages) => {
        this.messages = messages;
        this.scrollToEnd();
      }
    });
  }

  ngOnDestroy(): void {
    this.userSub?.unsubscribe();
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  send(): void {
    const text = this.draft.trim();
    if (!text || this.sending) return;
    this.sending = true;
    this.draft = '';
    this.scrollToEnd();
    this.jobsService.sendChat(this.jobId, text, this.selectedItem?.id).subscribe({
      next: (response) => {
        this.messages = [...this.messages, response.user_message, response.assistant_message];
        this.sending = false;
        this.scrollToEnd();
        if (response.changed_item_ids.length || response.topics_changed) {
          this.changed.emit(response);
        }
      },
      error: (error) => {
        this.sending = false;
        this.draft = text;
        this.snackBar.open(error.error?.detail || 'The agent could not answer', 'Close', { duration: 6000 });
      }
    });
  }

  clear(): void {
    this.jobsService.clearChat(this.jobId).subscribe({
      next: () => this.messages = [],
      error: () => this.snackBar.open('Failed to clear the conversation', 'Close', { duration: 3000 })
    });
  }

  private scrollToEnd(): void {
    setTimeout(() => {
      const el = this.transcript?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    }, 0);
  }
}
