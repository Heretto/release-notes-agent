import { Routes } from '@angular/router';
import { AuthGuard } from './core/auth/auth.guard';
import { AdminGuard } from './core/auth/admin.guard';
import { SuperuserGuard } from './core/auth/superuser.guard';

export const routes: Routes = [
  // Public routes (no layout)
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login.component').then(m => m.LoginComponent)
  },
  {
    path: 'invite/:token',
    loadComponent: () => import('./features/invitations/accept-invitation.component').then(m => m.AcceptInvitationComponent)
  },
  {
    path: 'forgot-password',
    loadComponent: () => import('./features/auth/forgot-password.component').then(m => m.ForgotPasswordComponent)
  },
  {
    path: 'reset-password',
    loadComponent: () => import('./features/auth/reset-password.component').then(m => m.ResetPasswordComponent)
  },
  
  // Protected routes (with layout)
  {
    path: '',
    loadComponent: () => import('./layouts/main-layout.component').then(m => m.MainLayoutComponent),
    canActivate: [AuthGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent)
      },
      {
        path: 'credentials',
        loadComponent: () => import('./features/credentials/credentials.component').then(m => m.CredentialsComponent)
      },
      {
        path: 'instructions',
        loadComponent: () => import('./features/instructions/instructions.component').then(m => m.InstructionsComponent)
      },
      {
        path: 'jobs',
        loadComponent: () => import('./features/jobs/jobs.component').then(m => m.JobsComponent)
      },
      {
        path: 'jobs/:id',
        loadComponent: () => import('./features/jobs/job-detail.component').then(m => m.JobDetailComponent)
      },
      {
        path: 'settings',
        loadComponent: () => import('./features/settings/settings.component').then(m => m.SettingsComponent)
      },
      {
        path: 'account',
        loadComponent: () => import('./features/account/account.component').then(m => m.AccountComponent)
      },
      {
        path: 'admin',
        canActivate: [AdminGuard],
        loadComponent: () => import('./features/admin/admin.component').then(m => m.AdminComponent)
      },
      {
        path: 'superadmin',
        canActivate: [SuperuserGuard],
        loadComponent: () => import('./features/superadmin/superadmin.component').then(m => m.SuperadminComponent)
      },
      {
        path: 'superadmin/:id',
        canActivate: [SuperuserGuard],
        loadComponent: () => import('./features/superadmin/superadmin-org-detail.component').then(m => m.SuperadminOrgDetailComponent)
      },
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full'
      }
    ]
  },
  
  // Default redirect
  {
    path: '',
    redirectTo: '/dashboard',
    pathMatch: 'full'
  },
  {
    path: '**',
    redirectTo: '/dashboard'
  }
];