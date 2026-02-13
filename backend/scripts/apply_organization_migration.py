#!/usr/bin/env python3
"""
Apply organization migration to the database.
This script applies the necessary schema changes for organization support.
"""

import sys
from pathlib import Path
import uuid
from datetime import datetime

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config import get_settings

def apply_migration():
    """Apply the organization migration to the database."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()
        
        try:
            # Check if migration is already applied
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'organizations'
                )
            """)).scalar()
            
            if result:
                print("✅ Organizations table already exists. Migration may have been applied.")
                
                # Check if current_organization_id column exists in users table
                col_exists = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'users' 
                        AND column_name = 'current_organization_id'
                    )
                """)).scalar()
                
                if col_exists:
                    print("✅ Migration already fully applied.")
                    return
            
            print("🔄 Creating organizations table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS organizations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    slug VARCHAR(255) UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE
                )
            """))
            
            print("🔄 Creating user_organizations association table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_organizations (
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    role VARCHAR(50) DEFAULT 'member',
                    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, organization_id)
                )
            """))
            
            # Check if current_organization_id already exists
            col_exists = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    AND column_name = 'current_organization_id'
                )
            """)).scalar()
            
            if not col_exists:
                print("🔄 Adding current_organization_id to users table...")
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN current_organization_id UUID REFERENCES organizations(id)
                """))
            
            # Check if organization_id exists in credentials
            cred_org_exists = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'credentials' 
                    AND column_name = 'organization_id'
                )
            """)).scalar()
            
            if not cred_org_exists:
                print("🔄 Adding organization_id and created_by to credentials table...")
                conn.execute(text("""
                    ALTER TABLE credentials 
                    ADD COLUMN organization_id UUID,
                    ADD COLUMN created_by VARCHAR(255)
                """))
            
            # Create default organization
            print("🔄 Creating default organization...")
            default_org_id = '00000000-0000-0000-0000-000000000001'
            
            # Check if default org already exists
            org_exists = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM organizations WHERE id = :org_id
                )
            """), {"org_id": default_org_id}).scalar()
            
            if not org_exists:
                conn.execute(text("""
                    INSERT INTO organizations (id, name, slug, is_active)
                    VALUES (:id, :name, :slug, :is_active)
                """), {
                    "id": default_org_id,
                    "name": "Default Organization",
                    "slug": "default",
                    "is_active": True
                })
            
            print("🔄 Associating existing users with default organization...")
            # Only add users not already in user_organizations
            conn.execute(text("""
                INSERT INTO user_organizations (user_id, organization_id, role)
                SELECT u.id, :org_id, 'member'
                FROM users u
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_organizations uo 
                    WHERE uo.user_id = u.id AND uo.organization_id = :org_id
                )
            """), {"org_id": default_org_id})
            
            print("🔄 Updating users to have default organization as current...")
            conn.execute(text("""
                UPDATE users 
                SET current_organization_id = :org_id
                WHERE current_organization_id IS NULL
            """), {"org_id": default_org_id})
            
            print("🔄 Updating credentials to belong to default organization...")
            conn.execute(text("""
                UPDATE credentials c
                SET organization_id = :org_id,
                    created_by = (SELECT email FROM users WHERE users.id = c.user_id)
                WHERE organization_id IS NULL
            """), {"org_id": default_org_id})
            
            # Now make organization_id NOT NULL if not already
            if not cred_org_exists:
                print("🔄 Making organization_id NOT NULL in credentials...")
                conn.execute(text("""
                    ALTER TABLE credentials 
                    ALTER COLUMN organization_id SET NOT NULL
                """))
                
                # Add foreign key constraint if not exists
                conn.execute(text("""
                    ALTER TABLE credentials 
                    ADD CONSTRAINT fk_credentials_org 
                    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                """))
            
            # Make user_id nullable in credentials (since they're org-owned)
            print("🔄 Making user_id nullable in credentials...")
            conn.execute(text("""
                ALTER TABLE credentials 
                ALTER COLUMN user_id DROP NOT NULL
            """))
            
            # Commit the transaction
            trans.commit()
            print("✅ Migration successfully applied!")
            
        except Exception as e:
            print(f"❌ Error applying migration: {e}")
            trans.rollback()
            raise

if __name__ == "__main__":
    try:
        apply_migration()
    except Exception as e:
        print(f"❌ Failed to apply migration: {e}")
        sys.exit(1)