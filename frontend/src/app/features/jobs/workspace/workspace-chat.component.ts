import { Component, ElementRef, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges, ViewChild, inject, ChangeDetectionStrategy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar } from '@angular/material/snack-bar';
import { JobsService, ChatMessage, ChatSendResponse, ReleaseNoteItem } from '../../../core/services/jobs.service';

@Component({
  selector: 'app-workspace-chat',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatIconModule, MatTooltipModule],
  template: `
    <div class="chat">
      <div class="chat-head">
        <div>
          <strong>{{ agentName || 'Writer agent' }}</strong>
          <div class="muted">
            @if (selectedItem) {
              Talking about “{{ selectedItem.title }}”
            } @else {
              Ask for changes to any note, or select one to talk about it
            }
          </div>
        </div>
        <button mat-icon-button matTooltip="Clear conversation" (click)="clear()" [disabled]="messages.length === 0 || sending">
          <mat-icon>delete_sweep</mat-icon>
        </button>
      </div>

      <div class="transcript" #transcript>
        @if (messages.length === 0) {
          <div class="empty">
            <mat-icon>forum</mat-icon>
            <p>Try: “Make the first note shorter”, “Move the API changes into their own group”,
              “Split the notes into one topic per group”, or “What changed in MARS-76?”</p>
          </div>
        }
        @for (message of messages; track message.id) {
          <div class="turn" [class.user]="message.role === 'user'" [class.assistant]="message.role === 'assistant'">
            <div class="bubble">{{ message.content }}</div>
            @if (message.actions?.length) {
              <ul class="actions">
                @for (action of message.actions; track $index) {
                  <li [class.failed]="!action.ok">
                    <mat-icon>{{ action.ok ? 'check_circle' : 'error' }}</mat-icon>
                    <span>{{ action.description || action.result }}</span>
                  </li>
                }
              </ul>
            }
          </div>
        }
        @if (sending) {
          <div class="turn assistant">
            <div class="bubble thinking" role="status" aria-label="The agent is working on a reply">
              <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
          </div>
        }
      </div>

      <form class="composer" (ngSubmit)="send()">
        <textarea [(ngModel)]="draft" name="draft" rows="2" placeholder="Ask the agent to change the release notes…"
                  (keydown)="onKeydown($event)" [disabled]="sending || disabled"></textarea>
        <button mat-icon-button color="primary" type="submit" [disabled]="!draft.trim() || sending || disabled" matTooltip="Send (Enter)">
          <mat-icon>send</mat-icon>
        </button>
      </form>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.Eager,
  styles: [`
    :host { display: block; height: 100%; }
    .chat { display: flex; flex-direction: column; height: 100%; min-height: 0; }
    .chat-head { display: flex; justify-content: space-between; align-items: flex-start; padding: 12px 16px; border-bottom: 1px solid var(--border-default); gap: 8px; }
    .muted { color: var(--text-tertiary); font-size: 12px; }
    .transcript { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; min-height: 0; }
    .empty { color: var(--text-tertiary); text-align: center; padding: 32px 12px; font-size: 13px; }
    .empty mat-icon { font-size: 36px; width: 36px; height: 36px; margin-bottom: 8px; }
    .turn { display: flex; flex-direction: column; max-width: 92%; }
    .turn.user { align-self: flex-end; align-items: flex-end; }
    .turn.assistant { align-self: flex-start; align-items: flex-start; }
    .bubble { padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
    .turn.user .bubble { background: var(--color-primary); color: white; border-bottom-right-radius: 4px; }
    .turn.assistant .bubble { background: var(--bg-secondary); color: var(--text-primary); border-bottom-left-radius: 4px; }
    .bubble.thinking { display: inline-flex; align-items: center; gap: 5px; padding: 12px 14px; }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-tertiary);
      animation: chat-bounce 1.3s infinite ease-in-out; }
    .dot:nth-child(2) { animation-delay: 0.15s; }
    .dot:nth-child(3) { animation-delay: 0.3s; }
    @keyframes chat-bounce {
      0%, 60%, 100% { transform: translateY(0); opacity: 0.45; }
      30% { transform: translateY(-4px); opacity: 1; }
    }
    /* Someone who asked for less motion still needs to see that it is working. */
    @media (prefers-reduced-motion: reduce) {
      .dot { animation: none; opacity: 0.6; }
    }
    .actions { list-style: none; margin: 6px 0 0 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
    .actions li { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-secondary); }
    .actions li mat-icon { font-size: 14px; width: 14px; height: 14px; color: var(--color-success); }
    .actions li.failed mat-icon { color: var(--color-error); }
    .composer { display: flex; align-items: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border-default); }
    .composer textarea { flex: 1; resize: none; border: 1px solid var(--border-strong); border-radius: 8px; padding: 10px 12px; font: inherit; font-size: 14px; background: var(--bg-primary); color: var(--text-primary); }
    .composer textarea:focus { outline: none; border-color: var(--border-focus); box-shadow: var(--focus-ring); }
  `]
})
export class WorkspaceChatComponent implements OnInit, OnChanges {
  private jobsService = inject(JobsService);
  private snackBar = inject(MatSnackBar);

  @Input({ required: true }) jobId!: string;
  @Input() selectedItem: ReleaseNoteItem | null = null;
  @Input() agentName: string | null = null;
  @Input() disabled = false;
  /**
   * A message to ask the agent straight away — set when someone sends a reviewer's comment
   * over from the Details pane. It is sent rather than left in the composer: the point of
   * the button is "do this", and the transcript is where it stays visible and undoable.
   */
  @Input() pendingMessage: string | null = null;
  /** The agent changed notes and/or topics; the workspace reloads them. */
  @Output() changed = new EventEmitter<ChatSendResponse>();
  /** Sent — the workspace clears it so toggling the pane cannot send it twice. */
  @Output() pendingMessageSent = new EventEmitter<void>();

  @ViewChild('transcript') transcript?: ElementRef<HTMLDivElement>;

  messages: ChatMessage[] = [];
  draft = '';
  sending = false;

  ngOnInit(): void {
    this.jobsService.getChat(this.jobId).subscribe({
      next: (messages) => {
        this.messages = messages;
        this.scrollToEnd();
        // After the transcript loads, or the load would overwrite what the send appended.
        this.sendPending();
      },
      error: () => this.sendPending()
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    // Only fires when the chat pane is already open; switching to it builds the component
    // fresh and ngOnInit handles it instead.
    if (changes['pendingMessage'] && !changes['pendingMessage'].firstChange) this.sendPending();
  }

  private sendPending(): void {
    const message = (this.pendingMessage || '').trim();
    if (!message || this.sending) return;
    this.pendingMessage = null;
    this.pendingMessageSent.emit();
    this.draft = message;
    this.send();
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

    // Shown straight away rather than when the reply arrives: the agent can take many
    // seconds, and until now the message vanished from the box with nothing in its place.
    // The id is local; the server's own copy replaces it below.
    const pending: ChatMessage = { id: `pending-${Date.now()}`, role: 'user', content: text };
    this.messages = [...this.messages, pending];
    this.scrollToEnd();

    this.jobsService.sendChat(this.jobId, text, this.selectedItem?.id).subscribe({
      next: (response) => {
        this.messages = [
          ...this.messages.filter(message => message !== pending),
          response.user_message, response.assistant_message,
        ];
        this.sending = false;
        this.scrollToEnd();
        if (response.changed_item_ids.length || response.topics_changed) {
          this.changed.emit(response);
        }
      },
      error: (error) => {
        this.sending = false;
        // Nothing was said, so take the message back and give the text to the composer —
        // leaving it in the transcript would claim the agent had heard it.
        this.messages = this.messages.filter(message => message !== pending);
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
