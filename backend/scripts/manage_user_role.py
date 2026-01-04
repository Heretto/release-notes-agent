#!/usr/bin/env python3
"""
Comprehensive utility script to manage user roles in organizations.

Usage:
    python scripts/manage_user_role.py <command> [options]

Commands:
    promote     - Promote user to admin
    demote      - Demote admin to member
    list        - List users and their roles
    add         - Add user to organization
    remove      - Remove user from organization

Examples:
    python scripts/manage_user_role.py promote user@example.com --org "Acme Corp"
    python scripts/manage_user_role.py demote user@example.com --org "Acme Corp"
    python scripts/manage_user_role.py list --org "Acme Corp"
    python scripts/manage_user_role.py add user@example.com --org "Acme Corp" --role admin
    python scripts/manage_user_role.py remove user@example.com --org "Acme Corp"
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_settings
from app.models.database import User
from app.models.organization import Organization, OrganizationMember, OrganizationRole

class OrganizationRoleManager:
    def __init__(self):
        settings = get_settings()
        engine = create_engine(settings.database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.session = SessionLocal()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
    
    def _get_role_value(self, role) -> str:
        """Extract string value from role enum or string."""
        return role.value if hasattr(role, 'value') else str(role)
    
    def get_user(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.session.query(User).filter(User.email == email).first()
    
    def get_organization(self, name: str) -> Optional[Organization]:
        """Get organization by name."""
        return self.session.query(Organization).filter(Organization.name == name).first()
    
    def get_membership(self, user_id: str, org_id: str) -> Optional[OrganizationMember]:
        """Get membership for user in organization."""
        return self.session.query(OrganizationMember).filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == org_id
        ).first()
    
    def promote_to_admin(self, email: str, org_name: str) -> bool:
        """Promote user to admin role."""
        user = self.get_user(email)
        if not user:
            print(f"❌ User '{email}' not found")
            return False
        
        org = self.get_organization(org_name)
        if not org:
            print(f"❌ Organization '{org_name}' not found")
            return False
        
        membership = self.get_membership(user.id, org.id)
        if not membership:
            print(f"❌ User '{email}' is not a member of '{org_name}'")
            return False
        
        if self._get_role_value(membership.role) == 'admin':
            print(f"ℹ️  User '{email}' is already an admin in '{org_name}'")
            return True
        
        membership.role = OrganizationRole.ADMIN
        self.session.commit()
        print(f"✅ Promoted '{email}' to admin in '{org_name}'")
        return True
    
    def demote_to_member(self, email: str, org_name: str) -> bool:
        """Demote admin to member role."""
        user = self.get_user(email)
        if not user:
            print(f"❌ User '{email}' not found")
            return False
        
        org = self.get_organization(org_name)
        if not org:
            print(f"❌ Organization '{org_name}' not found")
            return False
        
        membership = self.get_membership(user.id, org.id)
        if not membership:
            print(f"❌ User '{email}' is not a member of '{org_name}'")
            return False
        
        if self._get_role_value(membership.role) == 'member':
            print(f"ℹ️  User '{email}' is already a member in '{org_name}'")
            return True
        
        # Check if this is the last admin
        admin_count = self.session.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.role == OrganizationRole.ADMIN
        ).count()
        
        if admin_count <= 1:
            print(f"❌ Cannot demote '{email}' - they are the last admin in '{org_name}'")
            return False
        
        membership.role = OrganizationRole.MEMBER
        self.session.commit()
        print(f"✅ Demoted '{email}' to member in '{org_name}'")
        return True
    
    def add_user_to_org(self, email: str, org_name: str, role: str = 'member') -> bool:
        """Add user to organization with specified role."""
        user = self.get_user(email)
        if not user:
            print(f"❌ User '{email}' not found. User must register first.")
            return False
        
        org = self.get_organization(org_name)
        if not org:
            print(f"❌ Organization '{org_name}' not found")
            return False
        
        existing = self.get_membership(user.id, org.id)
        if existing:
            role_str = self._get_role_value(existing.role)
            print(f"ℹ️  User '{email}' is already a member of '{org_name}' as {role_str}")
            return True
        
        # Convert string role to enum
        role_enum = OrganizationRole.ADMIN if role == 'admin' else OrganizationRole.MEMBER
        
        membership = OrganizationMember(
            user_id=user.id,
            organization_id=org.id,
            role=role_enum,
            joined_at=datetime.utcnow()
        )
        self.session.add(membership)
        self.session.commit()
        print(f"✅ Added '{email}' to '{org_name}' as {role}")
        return True
    
    def remove_user_from_org(self, email: str, org_name: str) -> bool:
        """Remove user from organization."""
        user = self.get_user(email)
        if not user:
            print(f"❌ User '{email}' not found")
            return False
        
        org = self.get_organization(org_name)
        if not org:
            print(f"❌ Organization '{org_name}' not found")
            return False
        
        membership = self.get_membership(user.id, org.id)
        if not membership:
            print(f"❌ User '{email}' is not a member of '{org_name}'")
            return False
        
        # Check if this is the last admin
        if self._get_role_value(membership.role) == 'admin':
            admin_count = self.session.query(OrganizationMember).filter(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.role == OrganizationRole.ADMIN
            ).count()
            
            if admin_count <= 1:
                print(f"❌ Cannot remove '{email}' - they are the last admin in '{org_name}'")
                return False
        
        # Check if this is the last member
        member_count = self.session.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org.id
        ).count()
        
        if member_count <= 1:
            print(f"⚠️  Warning: Removing the last member will leave the organization empty")
            response = input("Continue? (y/N): ")
            if response.lower() != 'y':
                print("Aborted")
                return False
        
        self.session.delete(membership)
        self.session.commit()
        print(f"✅ Removed '{email}' from '{org_name}'")
        return True
    
    def list_organization_members(self, org_name: Optional[str] = None) -> None:
        """List all members of an organization or all organizations."""
        if org_name:
            org = self.get_organization(org_name)
            if not org:
                print(f"❌ Organization '{org_name}' not found")
                return
            
            self._print_org_members(org)
        else:
            orgs = self.session.query(Organization).all()
            if not orgs:
                print("No organizations found")
                return
            
            for org in orgs:
                self._print_org_members(org)
                print()
    
    def _print_org_members(self, org: Organization) -> None:
        """Print members of a specific organization."""
        print(f"\n🏢 {org.name}")
        print("=" * 60)
        
        memberships = self.session.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org.id
        ).order_by(OrganizationMember.role.desc(), OrganizationMember.joined_at).all()
        
        if not memberships:
            print("  No members")
            return
        
        print(f"{'Email':<30} {'Role':<10} {'Joined':<20}")
        print("-" * 60)
        
        for membership in memberships:
            user = self.session.query(User).filter(User.id == membership.user_id).first()
            role_str = membership.role.value if hasattr(membership.role, 'value') else str(membership.role)
            role_icon = "👑" if role_str == 'admin' else "👤"
            joined_date = membership.joined_at.strftime("%Y-%m-%d %H:%M")
            print(f"{role_icon} {user.email:<28} {role_str:<10} {joined_date}")
        
        admin_count = sum(1 for m in memberships if (m.role.value if hasattr(m.role, 'value') else str(m.role)) == 'admin')
        member_count = sum(1 for m in memberships if (m.role.value if hasattr(m.role, 'value') else str(m.role)) == 'member')
        print("-" * 60)
        print(f"Total: {len(memberships)} users ({admin_count} admins, {member_count} members)")
    
    def list_user_organizations(self, email: str) -> None:
        """List all organizations a user belongs to."""
        user = self.get_user(email)
        if not user:
            print(f"❌ User '{email}' not found")
            return
        
        memberships = self.session.query(OrganizationMember).filter(
            OrganizationMember.user_id == user.id
        ).all()
        
        if not memberships:
            print(f"User '{email}' is not a member of any organization")
            return
        
        print(f"\n👤 Organizations for {email}")
        print("=" * 60)
        print(f"{'Organization':<30} {'Role':<10} {'Joined':<20}")
        print("-" * 60)
        
        for membership in memberships:
            org = self.session.query(Organization).filter(
                Organization.id == membership.organization_id
            ).first()
            role_icon = "👑" if membership.role == 'admin' else "👤"
            joined_date = membership.joined_at.strftime("%Y-%m-%d %H:%M")
            print(f"{role_icon} {org.name:<28} {membership.role:<10} {joined_date}")
        
        print("-" * 60)
        print(f"Total: {len(memberships)} organizations")

def main():
    parser = argparse.ArgumentParser(
        description='Manage user roles in organizations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Promote user to admin:
    python scripts/manage_user_role.py promote user@example.com --org "Acme Corp"
  
  Demote admin to member:
    python scripts/manage_user_role.py demote user@example.com --org "Acme Corp"
  
  Add user to organization:
    python scripts/manage_user_role.py add user@example.com --org "Acme Corp" --role admin
  
  Remove user from organization:
    python scripts/manage_user_role.py remove user@example.com --org "Acme Corp"
  
  List organization members:
    python scripts/manage_user_role.py list --org "Acme Corp"
    python scripts/manage_user_role.py list  # List all organizations
  
  List user's organizations:
    python scripts/manage_user_role.py list --user user@example.com
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Promote command
    promote_parser = subparsers.add_parser('promote', help='Promote user to admin')
    promote_parser.add_argument('email', help='User email address')
    promote_parser.add_argument('--org', required=True, help='Organization name')
    
    # Demote command
    demote_parser = subparsers.add_parser('demote', help='Demote admin to member')
    demote_parser.add_argument('email', help='User email address')
    demote_parser.add_argument('--org', required=True, help='Organization name')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add user to organization')
    add_parser.add_argument('email', help='User email address')
    add_parser.add_argument('--org', required=True, help='Organization name')
    add_parser.add_argument('--role', choices=['admin', 'member'], default='member', help='User role')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove user from organization')
    remove_parser.add_argument('email', help='User email address')
    remove_parser.add_argument('--org', required=True, help='Organization name')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List users and roles')
    list_group = list_parser.add_mutually_exclusive_group()
    list_group.add_argument('--org', help='Organization name')
    list_group.add_argument('--user', help='User email address')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        with OrganizationRoleManager() as manager:
            if args.command == 'promote':
                success = manager.promote_to_admin(args.email, args.org)
                sys.exit(0 if success else 1)
            
            elif args.command == 'demote':
                success = manager.demote_to_member(args.email, args.org)
                sys.exit(0 if success else 1)
            
            elif args.command == 'add':
                success = manager.add_user_to_org(args.email, args.org, args.role)
                sys.exit(0 if success else 1)
            
            elif args.command == 'remove':
                success = manager.remove_user_from_org(args.email, args.org)
                sys.exit(0 if success else 1)
            
            elif args.command == 'list':
                if args.user:
                    manager.list_user_organizations(args.user)
                else:
                    manager.list_organization_members(args.org)
                sys.exit(0)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()