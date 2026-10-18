import { Routes } from '@angular/router';
import { hopAuthGuard, hopAdminGuard, hopSuperuserGuard, HOP_AGENT_ROUTES } from '@heretto/hop-ui';

export const routes: Routes = [
  // Public routes (no layout)
  { path: 'login', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopLoginComponent) },
  { path: 'invite/:token', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopAcceptInvitationComponent) },
  { path: 'forgot-password', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopForgotPasswordComponent) },
  { path: 'reset-password', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopResetPasswordComponent) },
  { path: 'auth/sso/complete', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopSSOCallbackComponent) },

  // Protected, but deliberately outside the shell: review is a reading view for people who
  // are not working in the app, so it carries no navigation. It must sit before the shell
  // route or the shell would claim the URL and wrap it in the layout.
  {
    path: 'releases/:id/review',
    canActivate: [hopAuthGuard],
    loadComponent: () => import('./features/jobs/review/review.component').then(m => m.ReviewComponent),
  },

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
        loadComponent: () => import('@heretto/hop-ui').then(m => m.HopCredentialsComponent),
      },
      {
        path: 'instructions',
        loadComponent: () => import('./features/instructions/instructions.component').then(m => m.InstructionsComponent),
      },
      // The editor is a page, not a dialog: it carries the query, its variables, the
      // agents, the guidance and the topic layout, which is more than a modal can hold.
      {
        path: 'instructions/new',
        loadComponent: () => import('./features/instructions/instruction-editor.component').then(m => m.InstructionEditorComponent),
      },
      {
        path: 'instructions/:id',
        loadComponent: () => import('./features/instructions/instruction-editor.component').then(m => m.InstructionEditorComponent),
      },
      {
        path: 'agents',
        children: HOP_AGENT_ROUTES,
      },
      {
        path: 'releases',
        loadComponent: () => import('./features/jobs/jobs.component').then(m => m.JobsComponent),
      },
      {
        path: 'releases/:id',
        loadComponent: () => import('./features/jobs/job-detail.component').then(m => m.JobDetailComponent),
      },
      {
        path: 'releases/:id/workspace',
        loadComponent: () => import('./features/jobs/workspace/workspace.component').then(m => m.WorkspaceComponent),
      },
      // Redirects so links handed out while these lived at /jobs keep working.
      { path: 'jobs', redirectTo: 'releases', pathMatch: 'full' },
      { path: 'jobs/:id', redirectTo: 'releases/:id' },
      { path: 'jobs/:id/workspace', redirectTo: 'releases/:id/workspace' },
      {
        path: 'settings',
        loadComponent: () => import('./features/settings/settings.component').then(m => m.SettingsComponent),
      },
      { path: 'account', loadComponent: () => import('@heretto/hop-ui').then(m => m.HopAccountComponent) },
      { path: 'admin', canActivate: [hopAdminGuard], loadComponent: () => import('@heretto/hop-ui').then(m => m.HopAdminComponent) },
      // hop-ui's DTD-set list navigates to /admin/dtd-sets/:id. An app with its own routes
      // has to declare it (hop-core AGENTS.md, "Route the detail page") or opening a set
      // falls through to the wildcard below and lands on the dashboard.
      {
        path: 'admin/dtd-sets/:dtdSetId',
        canActivate: [hopAdminGuard],
        loadComponent: () => import('@heretto/hop-ui').then(m => m.HopDtdSetDetailComponent),
      },
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
