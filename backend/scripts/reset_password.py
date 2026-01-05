#!/usr/bin/env python3
"""
Utility script to reset user passwords in development mode.

Usage:
    python scripts/reset_password.py <email> [--password <password>]
    python scripts/reset_password.py --list  # List all users

Examples:
    python scripts/reset_password.py user@example.com
    python scripts/reset_password.py user@example.com --password newpass123
    python scripts/reset_password.py --list
"""

import sys
import os
import argparse
import getpass
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, Column, String, Boolean, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from app.config import get_settings
import hashlib
import uuid

# Create a simplified User model that matches the actual database
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

def get_password_hash(password: str) -> str:
    """Hash a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()


class PasswordManager:
    def __init__(self):
        settings = get_settings()
        engine = create_engine(settings.database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.session = SessionLocal()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
    
    def list_users(self):
        """List all users in the system."""
        users = self.session.query(User).order_by(User.created_at.desc()).all()
        
        if not users:
            print("No users found in the database")
            return
        
        print("\n👥 Registered Users")
        print("=" * 70)
        print(f"{'Email':<35} {'Active':<10} {'Super':<10} {'Created':<20}")
        print("-" * 70)
        
        for user in users:
            active_status = "✅ Yes" if user.is_active else "❌ No"
            super_status = "👑 Yes" if user.is_superuser else "   No"
            created_date = user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else "Unknown"
            print(f"{user.email:<35} {active_status:<10} {super_status:<10} {created_date}")
        
        print("-" * 70)
        print(f"Total: {len(users)} users")
    
    def reset_password(self, email: str, password: Optional[str] = None) -> bool:
        """Reset password for a user."""
        # Find user
        user = self.session.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ Error: User '{email}' not found")
            print("\n💡 Tip: Use --list to see all registered users")
            return False
        
        # Get password if not provided
        if not password:
            print(f"\n🔐 Resetting password for: {email}")
            print("-" * 40)
            
            while True:
                password = getpass.getpass("Enter new password (min 8 chars): ")
                
                if len(password) < 8:
                    print("❌ Password must be at least 8 characters long")
                    continue
                
                confirm = getpass.getpass("Confirm new password: ")
                
                if password != confirm:
                    print("❌ Passwords do not match. Try again.")
                    continue
                
                break
        else:
            # Validate provided password
            if len(password) < 8:
                print(f"❌ Error: Password must be at least 8 characters long")
                return False
        
        # Update password
        user.password_hash = get_password_hash(password)
        self.session.commit()
        
        print(f"\n✅ Password successfully reset for '{email}'")
        
        # Show user details
        print("\n📋 User Details:")
        print(f"  • Email: {user.email}")
        print(f"  • Active: {'Yes' if user.is_active else 'No'}")
        print(f"  • Superuser: {'Yes' if user.is_superuser else 'No'}")
        print(f"  • Created: {user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else 'Unknown'}")
        
        # Check if user has organization membership (if organizations table exists)
        try:
            # Check if organizations table exists
            result = self.session.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'organizations'
                    )
                """)
            ).scalar()
            
            if result:
                # Query the user_organizations association table
                org_result = self.session.execute(
                    text("""
                        SELECT o.name, uo.role 
                        FROM user_organizations uo
                        JOIN organizations o ON o.id = uo.organization_id
                        WHERE uo.user_id = :user_id
                    """),
                    {"user_id": user.id}
                ).fetchall()
                
                if org_result:
                    print(f"\n🏢 Organization Memberships:")
                    for org_name, role in org_result:
                        role_icon = "👑" if role == 'owner' else ("🛡️" if role == 'admin' else "👤")
                        print(f"  {role_icon} {org_name} ({role})")
        except Exception:
            # Organizations feature might not be set up yet
            pass
        
        print("\n📝 You can now log in with the new password")
        return True
    
    def activate_user(self, email: str) -> bool:
        """Activate a deactivated user account."""
        user = self.session.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ Error: User '{email}' not found")
            return False
        
        if user.is_active:
            print(f"ℹ️  User '{email}' is already active")
            return True
        
        user.is_active = True
        self.session.commit()
        print(f"✅ User '{email}' has been activated")
        return True
    
    def deactivate_user(self, email: str) -> bool:
        """Deactivate a user account."""
        user = self.session.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ Error: User '{email}' not found")
            return False
        
        if not user.is_active:
            print(f"ℹ️  User '{email}' is already deactivated")
            return True
        
        user.is_active = False
        self.session.commit()
        print(f"✅ User '{email}' has been deactivated")
        return True
    
    def make_superuser(self, email: str) -> bool:
        """Grant superuser privileges to a user."""
        user = self.session.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ Error: User '{email}' not found")
            return False
        
        if user.is_superuser:
            print(f"ℹ️  User '{email}' is already a superuser")
            return True
        
        user.is_superuser = True
        self.session.commit()
        print(f"✅ User '{email}' now has superuser privileges")
        return True
    
    def remove_superuser(self, email: str) -> bool:
        """Remove superuser privileges from a user."""
        user = self.session.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ Error: User '{email}' not found")
            return False
        
        if not user.is_superuser:
            print(f"ℹ️  User '{email}' is not a superuser")
            return True
        
        user.is_superuser = False
        self.session.commit()
        print(f"✅ Superuser privileges removed from '{email}'")
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Reset user passwords and manage user accounts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Reset password (interactive):
    python scripts/reset_password.py user@example.com
  
  Reset password (non-interactive):
    python scripts/reset_password.py user@example.com --password newpass123
  
  List all users:
    python scripts/reset_password.py --list
  
  Activate/deactivate user:
    python scripts/reset_password.py user@example.com --activate
    python scripts/reset_password.py user@example.com --deactivate
  
  Manage superuser status:
    python scripts/reset_password.py user@example.com --make-super
    python scripts/reset_password.py user@example.com --remove-super
  
  Reset password for all users (batch mode):
    python scripts/reset_password.py --reset-all --password defaultpass123
        """
    )
    
    parser.add_argument('email', nargs='?', help='Email address of the user')
    parser.add_argument('--password', help='New password (min 8 chars). If not provided, will prompt')
    parser.add_argument('--list', action='store_true', help='List all users')
    parser.add_argument('--activate', action='store_true', help='Activate user account')
    parser.add_argument('--deactivate', action='store_true', help='Deactivate user account')
    parser.add_argument('--make-super', action='store_true', help='Grant superuser privileges')
    parser.add_argument('--remove-super', action='store_true', help='Remove superuser privileges')
    parser.add_argument('--reset-all', action='store_true', help='Reset password for all users (requires --password)')
    
    args = parser.parse_args()
    
    # Check environment
    settings = get_settings()
    if settings.app_env == "production":
        print("⚠️  WARNING: This script should only be used in development!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted")
            sys.exit(0)
    
    try:
        with PasswordManager() as manager:
            # Handle list command
            if args.list:
                manager.list_users()
                sys.exit(0)
            
            # Handle reset all
            if args.reset_all:
                if not args.password:
                    print("❌ Error: --reset-all requires --password")
                    sys.exit(1)
                
                print(f"⚠️  WARNING: This will reset passwords for ALL users to '{args.password}'")
                response = input("Are you sure? (yes/no): ")
                if response.lower() != 'yes':
                    print("Aborted")
                    sys.exit(0)
                
                users = manager.session.query(User).all()
                for user in users:
                    user.password_hash = get_password_hash(args.password)
                manager.session.commit()
                print(f"✅ Reset passwords for {len(users)} users")
                sys.exit(0)
            
            # Require email for other commands
            if not args.email:
                parser.print_help()
                sys.exit(1)
            
            # Handle user management commands
            if args.activate:
                success = manager.activate_user(args.email)
                sys.exit(0 if success else 1)
            
            if args.deactivate:
                success = manager.deactivate_user(args.email)
                sys.exit(0 if success else 1)
            
            if args.make_super:
                success = manager.make_superuser(args.email)
                sys.exit(0 if success else 1)
            
            if args.remove_super:
                success = manager.remove_superuser(args.email)
                sys.exit(0 if success else 1)
            
            # Default: reset password
            success = manager.reset_password(args.email, args.password)
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()