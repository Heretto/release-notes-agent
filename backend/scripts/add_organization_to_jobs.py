#!/usr/bin/env python3
"""
Add organization_id column to jobs and instruction_sets tables.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config import get_settings

def main():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' AND column_name = 'organization_id'
        """))
        
        if not result.fetchone():
            print("Adding organization_id to jobs table...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN organization_id UUID 
                REFERENCES organizations(id) ON DELETE CASCADE
            """))
            conn.commit()
            print("✓ Added organization_id to jobs table")
        else:
            print("✓ organization_id already exists in jobs table")
        
        # Check instruction_sets table
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'instruction_sets' AND column_name = 'organization_id'
        """))
        
        if not result.fetchone():
            print("Adding organization_id to instruction_sets table...")
            conn.execute(text("""
                ALTER TABLE instruction_sets 
                ADD COLUMN organization_id UUID 
                REFERENCES organizations(id) ON DELETE CASCADE
            """))
            conn.commit()
            print("✓ Added organization_id to instruction_sets table")
        else:
            print("✓ organization_id already exists in instruction_sets table")
        
        # Update existing records to use the user's organization
        print("\nUpdating existing records to set organization_id...")
        
        # Update instruction_sets
        conn.execute(text("""
            UPDATE instruction_sets 
            SET organization_id = (
                SELECT uo.organization_id 
                FROM user_organizations uo 
                WHERE uo.user_id = instruction_sets.user_id 
                LIMIT 1
            )
            WHERE organization_id IS NULL
        """))
        conn.commit()
        
        # Update jobs
        conn.execute(text("""
            UPDATE jobs 
            SET organization_id = (
                SELECT uo.organization_id 
                FROM user_organizations uo 
                WHERE uo.user_id = jobs.user_id 
                LIMIT 1
            )
            WHERE organization_id IS NULL
        """))
        conn.commit()
        
        print("✓ Updated existing records with organization_id")
        print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    main()