import { Routes } from '@angular/router';
import { hopAuthGuard, hopAdminGuard, hopSuperuserGuard } from '@heretto/hop-ui';

export const routes: Routes = [
  // Public routes (no layout)
  { path: 'login', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopLoginComponent) },
  { path: 'invite/:token', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopAcceptInvitationComponent) },
  { path: 'forgot-password', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopForgotPasswordComponent) },
  { path: 'reset-password', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopResetPasswordComponent) },
  { path: 'auth/sso/complete', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopSSOCallbackComponent) },

  // Protected routes (with layout)
  {
    path: '',
    canActivate: [hopAuthGuard],
    loadComponent: () => import('./shell/shell.component').then(m => m.ShellComponent),
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
      { path: 'account', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopAccountComponent) },
      { path: 'admin', canActivate: [hopAdminGuard], loadComponent: () => import('@heretto/hop-ui').then(m => m.HopAdminComponent) },
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
