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
import { OrganizationService, Organization } from '../core/services/organization.service';
import { AccountService } from '../core/services/account.service';

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
          <a mat-list-item routerLink="/account" routerLinkActive="active">
            <mat-icon matListItemIcon>account_circle</mat-icon>
            <span matListItemTitle>Account</span>
          </a>
          <a mat-list-item routerLink="/admin" routerLinkActive="active" *ngIf="isAdmin$ | async">
            <mat-icon matListItemIcon>admin_panel_settings</mat-icon>
            <span matListItemTitle>Administration</span>
          </a>
          <a mat-list-item routerLink="/superadmin" routerLinkActive="active" *ngIf="isSuperuser$ | async">
            <mat-icon matListItemIcon>security</mat-icon>
            <span matListItemTitle>System Admin</span>
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
              <!-- Org Switcher -->
              <ng-container *ngIf="userOrganizations.length > 1">
                <div class="org-switch-label" mat-menu-item disabled>
                  <small>Switch Organization</small>
                </div>
                <button mat-menu-item *ngFor="let switchOrg of userOrganizations"
                        [disabled]="switchOrg.id === org.id"
                        (click)="switchToOrg(switchOrg)">
                  <mat-icon>{{ switchOrg.id === org.id ? 'check' : 'business' }}</mat-icon>
                  <span>{{ switchOrg.name }}</span>
                </button>
                <mat-divider></mat-divider>
              </ng-container>
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

    .org-switch-label {
      cursor: default;
      opacity: 0.7;
    }
  `]
})
export class MainLayoutComponent implements OnInit {
  private authService = inject(AuthService);
  private organizationService = inject(OrganizationService);
  private accountService = inject(AccountService);

  currentOrganization$ = this.organizationService.currentOrganization$;
  isAdmin$ = this.accountService.isAdmin$;
  isSuperuser$ = this.accountService.isSuperuser$;
  userOrganizations: Organization[] = [];

  ngOnInit() {
    this.loadUserData();
  }

  logout() {
    this.accountService.clearAccountInfo();
    this.authService.logout();
  }

  switchToOrg(org: Organization) {
    this.organizationService.switchOrganization(org.id).subscribe({
      next: (response) => {
        this.authService.updateTokens(response);
        // Reload the page to refresh all data with new org context
        window.location.reload();
      },
      error: (error) => {
        console.error('Failed to switch organization:', error);
      }
    });
  }

  private loadUserData() {
    this.accountService.getAccountInfo().subscribe({
      next: () => {
        this.loadOrganizationData();
        this.loadUserOrganizations();
      },
      error: (error) => {
        console.error('Failed to load account info:', error);
      }
    });
  }

  private loadOrganizationData() {
    this.organizationService.getCurrentOrganization().subscribe({
      error: (error) => {
        console.error('Failed to load organization:', error);
      }
    });
  }

  private loadUserOrganizations() {
    this.organizationService.listUserOrganizations().subscribe({
      next: (orgs) => {
        this.userOrganizations = orgs;
      },
      error: (error) => {
        console.error('Failed to load user organizations:', error);
      }
    });
  }
}