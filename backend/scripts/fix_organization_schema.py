#!/usr/bin/env python3
"""
Fix organization schema in the database.
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config import get_settings

def fix_schema():
    """Fix the organization schema."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        trans = conn.begin()
        
        try:
            print("🔍 Checking current organizations table structure...")
            
            # Get columns of organizations table
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'organizations'
                ORDER BY ordinal_position
            """))
            
            existing_columns = {row[0] for row in result}
            print(f"   Existing columns: {existing_columns}")
            
            # Add missing columns
            if 'is_active' not in existing_columns:
                print("🔄 Adding is_active column...")
                conn.execute(text("""
                    ALTER TABLE organizations 
                    ADD COLUMN is_active BOOLEAN DEFAULT true
                """))
            
            if 'created_at' not in existing_columns:
                print("🔄 Adding created_at column...")
                conn.execute(text("""
                    ALTER TABLE organizations 
                    ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                """))
            
            if 'updated_at' not in existing_columns:
                print("🔄 Adding updated_at column...")
                conn.execute(text("""
                    ALTER TABLE organizations 
                    ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE
                """))
            
            # Check if user_organizations exists
            uo_exists = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'user_organizations'
                )
            """)).scalar()
            
            if not uo_exists:
                print("🔄 Creating user_organizations table...")
                conn.execute(text("""
                    CREATE TABLE user_organizations (
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                        role VARCHAR(50) DEFAULT 'member',
                        joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, organization_id)
                    )
                """))
            
            # Check current_organization_id in users
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
            
            # Check credentials columns
            cred_columns = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'credentials'
            """)).fetchall()
            cred_columns_set = {row[0] for row in cred_columns}
            
            if 'organization_id' not in cred_columns_set:
                print("🔄 Adding organization_id to credentials...")
                conn.execute(text("""
                    ALTER TABLE credentials 
                    ADD COLUMN organization_id UUID
                """))
            
            if 'created_by' not in cred_columns_set:
                print("🔄 Adding created_by to credentials...")
                conn.execute(text("""
                    ALTER TABLE credentials 
                    ADD COLUMN created_by VARCHAR(255)
                """))
            
            # Create or ensure default organization exists
            default_org_id = '00000000-0000-0000-0000-000000000001'
            
            org_exists = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM organizations WHERE id = :org_id
                )
            """), {"org_id": default_org_id}).scalar()
            
            if not org_exists:
                print("🔄 Creating default organization...")
                conn.execute(text("""
                    INSERT INTO organizations (id, name, slug, is_active)
                    VALUES (:id, :name, :slug, true)
                """), {
                    "id": default_org_id,
                    "name": "Default Organization",
                    "slug": "default"
                })
            else:
                print("✅ Default organization already exists")
            
            # Associate users with default organization
            print("🔄 Associating users with default organization...")
            conn.execute(text("""
                INSERT INTO user_organizations (user_id, organization_id, role)
                SELECT u.id, :org_id, 'member'
                FROM users u
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_organizations uo 
                    WHERE uo.user_id = u.id AND uo.organization_id = :org_id
                )
            """), {"org_id": default_org_id})
            
            # Update users to have default organization
            print("🔄 Setting current organization for users...")
            conn.execute(text("""
                UPDATE users 
                SET current_organization_id = :org_id
                WHERE current_organization_id IS NULL
            """), {"org_id": default_org_id})
            
            # Update credentials to belong to default organization
            print("🔄 Updating credentials organization...")
            conn.execute(text("""
                UPDATE credentials c
                SET organization_id = :org_id,
                    created_by = COALESCE(created_by, (SELECT email FROM users WHERE users.id = c.user_id))
                WHERE organization_id IS NULL
            """), {"org_id": default_org_id})
            
            # Check if we can make organization_id NOT NULL
            null_org_creds = conn.execute(text("""
                SELECT COUNT(*) FROM credentials WHERE organization_id IS NULL
            """)).scalar()
            
            if null_org_creds == 0:
                print("🔄 Making organization_id NOT NULL...")
                conn.execute(text("""
                    ALTER TABLE credentials 
                    ALTER COLUMN organization_id SET NOT NULL
                """))
                
                # Check if constraint exists
                constraint_exists = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.table_constraints 
                        WHERE constraint_name = 'fk_credentials_org'
                    )
                """)).scalar()
                
                if not constraint_exists:
                    conn.execute(text("""
                        ALTER TABLE credentials 
                        ADD CONSTRAINT fk_credentials_org 
                        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                    """))
            
            # Make user_id nullable in credentials
            print("🔄 Making user_id nullable in credentials...")
            conn.execute(text("""
                ALTER TABLE credentials 
                ALTER COLUMN user_id DROP NOT NULL
            """))
            
            trans.commit()
            print("✅ Schema successfully fixed!")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            trans.rollback()
            raise

if __name__ == "__main__":
    try:
        fix_schema()
        print("\n✅ Database schema is now compatible with the application!")
    except Exception as e:
        print(f"❌ Failed: {e}")
        sys.exit(1)