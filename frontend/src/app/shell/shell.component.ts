import { Component, OnInit, inject, ChangeDetectionStrategy } from '@angular/core';
import { HopMainLayoutComponent, NavItem } from '@heretto/hop-ui';
import { PeopleService } from '../core/services/people.service';

@Component({
  selector: 'app-shell',
  imports: [HopMainLayoutComponent],
  changeDetection: ChangeDetectionStrategy.Eager,
  template: `
    <hop-main-layout
      appTitle="AI Release Notes Agent"
      [navItems]="navItems">
    </hop-main-layout>
  `,
})
export class ShellComponent implements OnInit {
  private people = inject(PeopleService);

  ngOnInit(): void {
    // People manages the author/reviewer role, which only an organization admin can change.
    this.people.myRole().subscribe({
      next: role => {
        if (role.is_org_admin && !this.navItems.some(item => item.route === '/people')) {
          this.navItems = [...this.navItems, { label: 'People', route: '/people', icon: 'group' }];
        }
      },
      error: () => undefined
    });
  }

  // The layout appends Account / Administration / System Admin itself, role-gated —
  // do not re-add them here.
  navItems: NavItem[] = [
    { label: 'Dashboard', route: '/dashboard', icon: 'dashboard' },
    { label: 'Releases', route: '/releases', icon: 'rocket_launch' },
    { label: 'Instructions', route: '/instructions', icon: 'description' },
    { label: 'Agents', route: '/agents', icon: 'smart_toy' },
    { label: 'Credentials', route: '/credentials', icon: 'vpn_key' },
  ];
}
