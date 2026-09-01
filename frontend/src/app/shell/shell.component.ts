import { Component } from '@angular/core';
import { HopMainLayoutComponent, NavItem } from '@heretto/hop-ui';

@Component({
  selector: 'app-shell',
  imports: [HopMainLayoutComponent],
  template: `
    <hop-main-layout
      appTitle="AI Release Notes Agent"
      [navItems]="navItems">
    </hop-main-layout>
  `,
})
export class ShellComponent {
  // The layout appends Account / Administration / System Admin itself, role-gated —
  // do not re-add them here.
  navItems: NavItem[] = [
    { label: 'Dashboard', route: '/dashboard', icon: 'dashboard' },
    { label: 'Jobs', route: '/jobs', icon: 'work' },
    { label: 'Instructions', route: '/instructions', icon: 'description' },
    { label: 'Credentials', route: '/credentials', icon: 'vpn_key' },
  ];
}
