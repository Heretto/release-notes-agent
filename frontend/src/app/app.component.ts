import { Component, inject } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from './core/auth/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatToolbarModule,
    MatSidenavModule,
    MatListModule,
    MatIconModule,
    MatButtonModule
  ],
  template: `
    <mat-sidenav-container class="sidenav-container">
      <mat-sidenav #sidenav mode="side" [opened]="isAuthenticated()" class="sidenav">
        <mat-nav-list>
          <a mat-list-item routerLink="/dashboard" routerLinkActive="active">
            <mat-icon matListItemIcon>dashboard</mat-icon>
            <span matListItemTitle>Dashboard</span>
          </a>
          <a mat-list-item routerLink="/jobs" routerLinkActive="active">
            <mat-icon matListItemIcon>work</mat-icon>
            <span matListItemTitle>Jobs</span>
          </a>
          <a mat-list-item routerLink="/instructions" routerLinkActive="active">
            <mat-icon matListItemIcon>description</mat-icon>
            <span matListItemTitle>Instructions</span>
          </a>
          <a mat-list-item routerLink="/credentials" routerLinkActive="active">
            <mat-icon matListItemIcon>vpn_key</mat-icon>
            <span matListItemTitle>Credentials</span>
          </a>
          <a mat-list-item routerLink="/settings" routerLinkActive="active">
            <mat-icon matListItemIcon>settings</mat-icon>
            <span matListItemTitle>Settings</span>
          </a>
          <a mat-list-item routerLink="/account" routerLinkActive="active">
            <mat-icon matListItemIcon>account_circle</mat-icon>
            <span matListItemTitle>Account</span>
          </a>
        </mat-nav-list>
      </mat-sidenav>
      
      <mat-sidenav-content>
        <mat-toolbar color="primary">
          <button 
            mat-icon-button 
            (click)="sidenav.toggle()"
            *ngIf="isAuthenticated()">
            <mat-icon>menu</mat-icon>
          </button>
          <span>AI Release Notes Agent</span>
          <span class="spacer"></span>
          <button 
            mat-button 
            (click)="logout()"
            *ngIf="isAuthenticated()">
            <mat-icon>logout</mat-icon>
            Logout
          </button>
        </mat-toolbar>
        
        <div class="content">
          <router-outlet></router-outlet>
        </div>
      </mat-sidenav-content>
    </mat-sidenav-container>
  `,
  styles: [`
    .sidenav-container {
      height: 100%;
    }
    
    .sidenav {
      width: 250px;
    }
    
    .spacer {
      flex: 1 1 auto;
    }
    
    .content {
      padding: 20px;
    }
    
    .active {
      background-color: rgba(63, 81, 181, 0.1);
    }
  `]
})
export class AppComponent {
  private authService = inject(AuthService);
  
  isAuthenticated() {
    return this.authService.isAuthenticated();
  }
  
  logout() {
    this.authService.logout();
  }
}