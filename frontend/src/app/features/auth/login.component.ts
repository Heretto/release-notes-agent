import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../core/auth/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule
  ],
  template: `
    <div class="login-container">
      <mat-card class="login-card">
        <mat-card-header>
          <mat-card-title>{{ isRegisterMode ? 'Create Account' : 'Login' }}</mat-card-title>
        </mat-card-header>
        
        <mat-card-content>
          <form [formGroup]="loginForm" (ngSubmit)="onSubmit()">
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Email</mat-label>
              <input matInput type="email" formControlName="email" required>
              <mat-error *ngIf="loginForm.get('email')?.hasError('required')">
                Email is required
              </mat-error>
              <mat-error *ngIf="loginForm.get('email')?.hasError('email')">
                Please enter a valid email
              </mat-error>
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Password</mat-label>
              <input matInput [type]="hidePassword ? 'password' : 'text'" 
                     formControlName="password" required>
              <button mat-icon-button matSuffix (click)="hidePassword = !hidePassword" 
                      type="button">
                <mat-icon>{{hidePassword ? 'visibility_off' : 'visibility'}}</mat-icon>
              </button>
              <mat-error *ngIf="loginForm.get('password')?.hasError('required')">
                Password is required
              </mat-error>
            </mat-form-field>
            
            <div class="error-message" *ngIf="errorMessage">
              {{ errorMessage }}
            </div>
            
            <div class="button-row">
              <button mat-raised-button color="primary" type="submit" 
                      [disabled]="!loginForm.valid || loading">
                <mat-spinner diameter="20" *ngIf="loading"></mat-spinner>
                <span *ngIf="!loading">
                  {{ isRegisterMode ? 'Create Account' : 'Login' }}
                </span>
              </button>
              
              <button mat-button type="button" (click)="switchToRegister()">
                {{ isRegisterMode ? 'Already have an account?' : 'Create Account' }}
              </button>
            </div>
          </form>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .login-container {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .login-card {
      width: 100%;
      max-width: 400px;
      padding: 20px;
    }
    
    .full-width {
      width: 100%;
      margin-bottom: 15px;
    }
    
    .button-row {
      display: flex;
      justify-content: space-between;
      margin-top: 20px;
    }
    
    .error-message {
      color: #f44336;
      margin-bottom: 15px;
      text-align: center;
    }
    
    mat-spinner {
      display: inline-block;
      margin-right: 10px;
    }
  `]
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  
  hidePassword = true;
  loading = false;
  errorMessage = '';
  isRegisterMode = false;
  
  loginForm: FormGroup = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]]
  });
  
  onSubmit() {
    if (this.loginForm.valid) {
      this.loading = true;
      this.errorMessage = '';
      
      const { email, password } = this.loginForm.value;
      
      if (this.isRegisterMode) {
        this.authService.register(email, password).subscribe({
          next: () => {
            this.isRegisterMode = false;
            this.errorMessage = 'Account created! Please login.';
            this.loading = false;
          },
          error: (error) => {
            this.errorMessage = error.error.detail || 'Registration failed';
            this.loading = false;
          }
        });
      } else {
        this.authService.login(email, password).subscribe({
          next: () => {
            this.loading = false;
          },
          error: (error) => {
            this.errorMessage = error.error.detail || 'Login failed';
            this.loading = false;
          }
        });
      }
    }
  }
  
  switchToRegister() {
    this.isRegisterMode = !this.isRegisterMode;
    this.errorMessage = '';
  }
}