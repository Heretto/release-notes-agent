import { Routes } from '@angular/router';
import {
  HopLoginComponent,
  HopForgotPasswordComponent,
  HopResetPasswordComponent,
  HopSSOCallbackComponent,
  HopAcceptInvitationComponent,
  HopAccountComponent,
  HopAdminComponent,
  HopMainLayoutComponent,
  hopAuthGuard,
  hopAdminGuard,
  hopSuperuserGuard,
} from '@heretto/hop-ui';

const NAV_ITEMS = [
  { label: 'Dashboard', icon: 'dashboard', route: '/dashboard' },
  { label: 'Jobs', icon: 'work', route: '/jobs' },
  { label: 'Instructions', icon: 'description', route: '/instructions' },
  { label: 'Credentials', icon: 'vpn_key', route: '/credentials' },
];

export const routes: Routes = [
  // Public routes (no layout)
  { path: 'login', component: HopLoginComponent },
  { path: 'invite/:token', component: HopAcceptInvitationComponent },
  { path: 'forgot-password', component: HopForgotPasswordComponent },
  { path: 'reset-password', component: HopResetPasswordComponent },
  { path: 'auth/sso/complete', component: HopSSOCallbackComponent },

  // Protected routes (with layout)
  {
    path: '',
    component: HopMainLayoutComponent,
    canActivate: [hopAuthGuard],
    data: { appTitle: 'AI Release Notes Agent', navItems: NAV_ITEMS },
    children: [
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
      },
      {
        path: 'credentials',
        loadComponent: () => import('./features/credentials/credentials.component').then(m => m.CredentialsComponent),
      },
      {
        path: 'instructions',
        loadComponent: () => import('./features/instructions/instructions.component').then(m => m.InstructionsComponent),
      },
      {
        path: 'jobs',
        loadComponent: () => import('./features/jobs/jobs.component').then(m => m.JobsComponent),
      },
      {
        path: 'jobs/:id',
        loadComponent: () => import('./features/jobs/job-detail.component').then(m => m.JobDetailComponent),
      },
      {
        path: 'settings',
        loadComponent: () => import('./features/settings/settings.component').then(m => m.SettingsComponent),
      },
      { path: 'account', component: HopAccountComponent },
      { path: 'admin', canActivate: [hopAdminGuard], component: HopAdminComponent },
      {
        path: 'superadmin',
        canActivate: [hopSuperuserGuard],
        loadComponent: () => import('./features/superadmin/superadmin.component').then(m => m.SuperadminComponent),
      },
      {
        path: 'superadmin/:id',
        canActivate: [hopSuperuserGuard],
        loadComponent: () => import('./features/superadmin/superadmin-org-detail.component').then(m => m.SuperadminOrgDetailComponent),
      },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
    ],
  },

  { path: '', redirectTo: '/dashboard', pathMatch: 'full' },
  { path: '**', redirectTo: '/dashboard' },
];
