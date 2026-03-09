import { Component, inject, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';

export interface AddMemberDialogData {
  orgName: string;
}

export interface AddMemberDialogResult {
  mode: 'add' | 'invite';
  email: string;
  role: string;
}

@Component({
  selector: 'app-superadmin-add-member-dialog',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatDialogModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatTabsModule,
  ],
  template: `
    <h2 mat-dialog-title>Add Member to {{ data.orgName }}</h2>
    <mat-dialog-content>
      <mat-tab-group (selectedIndexChange)="onTabChange($event)">
        <mat-tab label="Add Existing User">
          <div class="tab-content">
            <p class="hint">Add a user who already has an account in the system.</p>
            <form [formGroup]="addForm">
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Email Address</mat-label>
                <input matInput type="email" formControlName="email" required>
                <mat-error *ngIf="addForm.get('email')?.hasError('required')">Email is required</mat-error>
                <mat-error *ngIf="addForm.get('email')?.hasError('email')">Enter a valid email</mat-error>
              </mat-form-field>
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Role</mat-label>
                <mat-select formControlName="role" required>
                  <mat-option value="member">Member</mat-option>
                  <mat-option value="admin">Administrator</mat-option>
                </mat-select>
              </mat-form-field>
            </form>
          </div>
        </mat-tab>
        <mat-tab label="Invite New User">
          <div class="tab-content">
            <p class="hint">Send an invitation to someone who doesn't have an account yet. They'll receive a link to create their account and join this organization.</p>
            <form [formGroup]="inviteForm">
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Email Address</mat-label>
                <input matInput type="email" formControlName="email" required>
                <mat-error *ngIf="inviteForm.get('email')?.hasError('required')">Email is required</mat-error>
                <mat-error *ngIf="inviteForm.get('email')?.hasError('email')">Enter a valid email</mat-error>
              </mat-form-field>
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Role</mat-label>
                <mat-select formControlName="role" required>
                  <mat-option value="member">Member</mat-option>
                  <mat-option value="admin">Administrator</mat-option>
                </mat-select>
              </mat-form-field>
            </form>
          </div>
        </mat-tab>
      </mat-tab-group>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
      <button mat-raised-button color="primary"
              [disabled]="!isValid()"
              (click)="onSubmit()">
        {{ selectedTab === 0 ? 'Add User' : 'Send Invitation' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .full-width {
      width: 100%;
      margin-bottom: 8px;
    }
    mat-dialog-content {
      min-width: 450px;
    }
    .tab-content {
      padding: 16px 0;
    }
    .hint {
      font-size: 13px;
      color: rgba(0, 0, 0, 0.54);
      margin-bottom: 16px;
    }
  `]
})
export class SuperadminAddMemberDialogComponent {
  private fb = inject(FormBuilder);
  private dialogRef = inject(MatDialogRef<SuperadminAddMemberDialogComponent>);

  selectedTab = 0;

  addForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    role: ['member', Validators.required]
  });

  inviteForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    role: ['member', Validators.required]
  });

  constructor(@Inject(MAT_DIALOG_DATA) public data: AddMemberDialogData) {}

  onTabChange(index: number) {
    this.selectedTab = index;
  }

  isValid(): boolean {
    return this.selectedTab === 0 ? this.addForm.valid : this.inviteForm.valid;
  }

  onCancel() {
    this.dialogRef.close();
  }

  onSubmit() {
    if (this.selectedTab === 0 && this.addForm.valid) {
      this.dialogRef.close({
        mode: 'add',
        email: this.addForm.value.email,
        role: this.addForm.value.role,
      } as AddMemberDialogResult);
    } else if (this.selectedTab === 1 && this.inviteForm.valid) {
      this.dialogRef.close({
        mode: 'invite',
        email: this.inviteForm.value.email,
        role: this.inviteForm.value.role,
      } as AddMemberDialogResult);
    }
  }
}
