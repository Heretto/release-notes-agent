import { Routes } from '@angular/router';
import { AuthGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login.component').then(m => m.LoginComponent)
  },
  {
    path: 'dashboard',
    loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
    canActivate: [AuthGuard]
  },
  {
    path: 'credentials',
    loadComponent: () => import('./features/credentials/credentials.component').then(m => m.CredentialsComponent),
    canActivate: [AuthGuard]
  },
  {
    path: 'instructions',
    loadComponent: () => import('./features/instructions/instructions.component').then(m => m.InstructionsComponent),
    canActivate: [AuthGuard]
  },
  {
    path: 'jobs',
    loadComponent: () => import('./features/jobs/jobs.component').then(m => m.JobsComponent),
    canActivate: [AuthGuard]
  },
  {
    path: 'jobs/:id',
    loadComponent: () => import('./features/jobs/job-detail.component').then(m => m.JobDetailComponent),
    canActivate: [AuthGuard]
  },
  {
    path: 'settings',
    loadComponent: () => import('./features/settings/settings.component').then(m => m.SettingsComponent),
    canActivate: [AuthGuard]
  },
  {
    path: 'account',
    loadComponent: () => import('./features/account/account.component').then(m => m.AccountComponent),
    canActivate: [AuthGuard]
  },
  {
    path: '',
    redirectTo: '/dashboard',
    pathMatch: 'full'
  }
];