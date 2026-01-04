#!/usr/bin/env python3
"""
Utility script to promote a user to admin role in an organization.

Usage:
    python scripts/promote_to_admin.py <user_email> [--org <organization_name>]

Examples:
    python scripts/promote_to_admin.py user@example.com
    python scripts/promote_to_admin.py user@example.com --org "Acme Corp"
"""

import sys
import os
import argparse
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.models.database import User
from app.models.organization import Organization, OrganizationMember

def get_session():
    """Create a database session."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def list_user_organizations(session, email: str):
    """List all organizations a user belongs to."""
    user = session.query(User).filter(User.email == email).first()
    if not user:
        return None, []
    
    memberships = session.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id
    ).all()
    
    organizations = []
    for membership in memberships:
        org = session.query(Organization).filter(
            Organization.id == membership.organization_id
        ).first()
        if org:
            organizations.append({
                'name': org.name,
                'role': membership.role,
                'id': str(org.id)
            })
    
    return user, organizations

def promote_user_to_admin(session, user_email: str, org_name: str = None):
    """Promote a user to admin role in an organization."""
    # Find the user
    user = session.query(User).filter(User.email == user_email).first()
    if not user:
        print(f"❌ Error: User with email '{user_email}' not found")
        return False
    
    # Get user's memberships
    memberships = session.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id
    ).all()
    
    if not memberships:
        print(f"❌ Error: User '{user_email}' is not a member of any organization")
        return False
    
    # If organization name is provided, find specific organization
    if org_name:
        org = session.query(Organization).filter(Organization.name == org_name).first()
        if not org:
            print(f"❌ Error: Organization '{org_name}' not found")
            return False
        
        membership = session.query(OrganizationMember).filter(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == org.id
        ).first()
        
        if not membership:
            print(f"❌ Error: User '{user_email}' is not a member of organization '{org_name}'")
            return False
        
        if membership.role == 'admin':
            print(f"ℹ️  User '{user_email}' is already an admin in '{org_name}'")
            return True
        
        # Promote to admin
        membership.role = 'admin'
        session.commit()
        print(f"✅ Successfully promoted '{user_email}' to admin in '{org_name}'")
        return True
    
    # If no organization specified and user belongs to only one org, use that
    if len(memberships) == 1:
        membership = memberships[0]
        org = session.query(Organization).filter(
            Organization.id == membership.organization_id
        ).first()
        
        if membership.role == 'admin':
            print(f"ℹ️  User '{user_email}' is already an admin in '{org.name}'")
            return True
        
        # Promote to admin
        membership.role = 'admin'
        session.commit()
        print(f"✅ Successfully promoted '{user_email}' to admin in '{org.name}'")
        return True
    
    # Multiple organizations - list them
    print(f"\n🏢 User '{user_email}' belongs to multiple organizations:")
    print("-" * 50)
    for membership in memberships:
        org = session.query(Organization).filter(
            Organization.id == membership.organization_id
        ).first()
        role_icon = "👑" if membership.role == 'admin' else "👤"
        print(f"  {role_icon} {org.name} (Role: {membership.role})")
    print("-" * 50)
    print("\n⚠️  Please specify the organization using --org <organization_name>")
    return False

def list_all_admins(session, org_name: str = None):
    """List all admins in an organization or all organizations."""
    if org_name:
        org = session.query(Organization).filter(Organization.name == org_name).first()
        if not org:
            print(f"❌ Error: Organization '{org_name}' not found")
            return
        
        admin_memberships = session.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.role == 'admin'
        ).all()
        
        print(f"\n👑 Admins in '{org_name}':")
        print("-" * 50)
        for membership in admin_memberships:
            user = session.query(User).filter(User.id == membership.user_id).first()
            print(f"  • {user.email}")
        if not admin_memberships:
            print("  No admins found")
        print("-" * 50)
    else:
        # List all organizations and their admins
        orgs = session.query(Organization).all()
        print("\n👑 Organization Admins:")
        print("=" * 60)
        for org in orgs:
            print(f"\n📁 {org.name}")
            print("-" * 40)
            admin_memberships = session.query(OrganizationMember).filter(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.role == 'admin'
            ).all()
            
            for membership in admin_memberships:
                user = session.query(User).filter(User.id == membership.user_id).first()
                print(f"  • {user.email}")
            if not admin_memberships:
                print("  No admins")
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(
        description='Promote a user to admin role in an organization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/promote_to_admin.py user@example.com
  python scripts/promote_to_admin.py user@example.com --org "Acme Corp"
  python scripts/promote_to_admin.py --list-admins
  python scripts/promote_to_admin.py --list-admins --org "Acme Corp"
  python scripts/promote_to_admin.py --list-user user@example.com
        """
    )
    
    parser.add_argument('email', nargs='?', help='Email address of the user to promote')
    parser.add_argument('--org', dest='organization', help='Name of the organization')
    parser.add_argument('--list-admins', action='store_true', help='List all admins')
    parser.add_argument('--list-user', dest='list_user', help='List organizations for a specific user')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.email and not args.list_admins and not args.list_user:
        parser.print_help()
        sys.exit(1)
    
    # Create database session
    session = get_session()
    
    try:
        if args.list_admins:
            list_all_admins(session, args.organization)
        elif args.list_user:
            user, orgs = list_user_organizations(session, args.list_user)
            if not user:
                print(f"❌ Error: User '{args.list_user}' not found")
            elif not orgs:
                print(f"❌ Error: User '{args.list_user}' is not a member of any organization")
            else:
                print(f"\n🏢 Organizations for '{args.list_user}':")
                print("-" * 50)
                for org in orgs:
                    role_icon = "👑" if org['role'] == 'admin' else "👤"
                    print(f"  {role_icon} {org['name']} (Role: {org['role']})")
                print("-" * 50)
        else:
            success = promote_user_to_admin(session, args.email, args.organization)
            sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    main()