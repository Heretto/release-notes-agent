import { Component, inject, OnInit } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { MatDividerModule } from '@angular/material/divider';
import { AuthService } from '../core/auth/auth.service';
import { OrganizationService } from '../core/services/organization.service';
import { AccountService } from '../core/services/account.service';
import { Observable } from 'rxjs';

@Component({
  selector: 'app-main-layout',
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
    MatButtonModule,
    MatMenuModule,
    MatDividerModule
  ],
  template: `
    <mat-sidenav-container class="sidenav-container">
      <mat-sidenav #sidenav mode="side" [opened]="true" class="sidenav">
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
          <a mat-list-item routerLink="/admin" routerLinkActive="active" *ngIf="isAdmin$ | async">
            <mat-icon matListItemIcon>admin_panel_settings</mat-icon>
            <span matListItemTitle>Administration</span>
          </a>
        </mat-nav-list>
      </mat-sidenav>
      
      <mat-sidenav-content>
        <mat-toolbar color="primary">
          <button 
            mat-icon-button 
            (click)="sidenav.toggle()">
            <mat-icon>menu</mat-icon>
          </button>
          <span>AI Release Notes Agent</span>
          <span class="spacer"></span>
          
          <!-- Organization Display -->
          <div class="organization-info" *ngIf="currentOrganization$ | async as org">
            <button mat-button [matMenuTriggerFor]="orgMenu">
              <mat-icon>business</mat-icon>
              <span class="org-name">{{ org.name }}</span>
              <mat-icon>arrow_drop_down</mat-icon>
            </button>
            <mat-menu #orgMenu="matMenu">
              <div mat-menu-item disabled class="org-menu-header">
                <strong>{{ org.name }}</strong>
              </div>
              <mat-divider></mat-divider>
              <button mat-menu-item routerLink="/admin" *ngIf="isAdmin$ | async">
                <mat-icon>admin_panel_settings</mat-icon>
                <span>Manage Organization</span>
              </button>
              <button mat-menu-item routerLink="/account">
                <mat-icon>account_circle</mat-icon>
                <span>My Account</span>
              </button>
              <mat-divider></mat-divider>
              <button mat-menu-item (click)="logout()">
                <mat-icon>logout</mat-icon>
                <span>Logout</span>
              </button>
            </mat-menu>
          </div>
          
          <button 
            mat-icon-button 
            (click)="logout()"
            *ngIf="!(currentOrganization$ | async)">
            <mat-icon>logout</mat-icon>
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
    
    .organization-info {
      display: flex;
      align-items: center;
      margin-right: 16px;
    }
    
    .org-name {
      margin: 0 8px;
      max-width: 200px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    
    .org-menu-header {
      padding: 8px 16px;
      cursor: default;
    }
  `]
})
export class MainLayoutComponent implements OnInit {
  private authService = inject(AuthService);
  private organizationService = inject(OrganizationService);
  private accountService = inject(AccountService);
  
  currentOrganization$ = this.organizationService.currentOrganization$;
  isAdmin$ = this.accountService.isAdmin$;
  
  ngOnInit() {
    this.loadUserData();
  }
  
  logout() {
    this.accountService.clearAccountInfo();
    this.authService.logout();
  }
  
  private loadUserData() {
    // Load account info (which includes role)
    this.accountService.getAccountInfo().subscribe({
      next: (info) => {
        // Account info loaded, now load organization
        this.loadOrganizationData();
      },
      error: (error) => {
        console.error('Failed to load account info:', error);
      }
    });
  }
  
  private loadOrganizationData() {
    this.organizationService.getCurrentOrganization().subscribe({
      next: (org) => {
        // Organization loaded successfully
      },
      error: (error) => {
        console.error('Failed to load organization:', error);
      }
    });
  }
}