"""Migrate existing users to organizations

Revision ID: migrate_existing_users_to_organizations
Revises: add_organizations
Create Date: 2026-01-02

This migration creates an organization for each existing user and makes them the admin.
It also updates all existing resources to belong to the user's organization.

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from sqlalchemy.dialects import postgresql
import uuid
import re


# revision identifiers, used by Alembic.
revision = 'migrate_existing_users_to_organizations'
down_revision = 'add_organizations'
branch_labels = None
depends_on = None


def create_slug(name):
    """Create a URL-safe slug from a name."""
    # Convert to lowercase and replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower())
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


def upgrade():
    # Get database connection
    connection = op.get_bind()
    
    # Fetch all existing users
    result = connection.execute(text("SELECT id, email FROM users"))
    users = result.fetchall()
    
    if users:
        print(f"Migrating {len(users)} existing users to organizations...")
        
        for user in users:
            user_id = user.id
            email = user.email
            
            # Create organization name from email (before @ symbol)
            org_name = email.split('@')[0] + "'s Organization"
            org_slug = create_slug(email.split('@')[0])
            
            # Ensure unique slug by appending UUID if necessary
            slug_check = connection.execute(
                text("SELECT COUNT(*) FROM organizations WHERE slug = :slug"),
                {"slug": org_slug}
            ).scalar()
            
            if slug_check > 0:
                # Append part of UUID to make unique
                org_slug = f"{org_slug}-{str(uuid.uuid4())[:8]}"
            
            # Create organization for this user
            org_id = str(uuid.uuid4())
            connection.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, created_at)
                    VALUES (:id, :name, :slug, NOW())
                """),
                {"id": org_id, "name": org_name, "slug": org_slug}
            )
            
            # Add user as admin of their organization
            connection.execute(
                text("""
                    INSERT INTO organization_members (id, organization_id, user_id, role, joined_at)
                    VALUES (:id, :org_id, :user_id, 'admin', NOW())
                """),
                {"id": str(uuid.uuid4()), "org_id": org_id, "user_id": user_id}
            )
            
            # Update all resources owned by this user to belong to their organization
            connection.execute(
                text("UPDATE credentials SET organization_id = :org_id WHERE user_id = :user_id"),
                {"org_id": org_id, "user_id": user_id}
            )
            
            connection.execute(
                text("UPDATE instruction_sets SET organization_id = :org_id WHERE user_id = :user_id"),
                {"org_id": org_id, "user_id": user_id}
            )
            
            connection.execute(
                text("UPDATE jobs SET organization_id = :org_id WHERE user_id = :user_id"),
                {"org_id": org_id, "user_id": user_id}
            )
            
            connection.execute(
                text("UPDATE webhook_configs SET organization_id = :org_id WHERE user_id = :user_id"),
                {"org_id": org_id, "user_id": user_id}
            )
            
            connection.execute(
                text("UPDATE dita_templates SET organization_id = :org_id WHERE user_id = :user_id"),
                {"org_id": org_id, "user_id": user_id}
            )
            
            print(f"Created organization '{org_name}' for user {email}")
        
        print("Migration completed successfully!")
    else:
        print("No existing users found. Skipping migration.")


def downgrade():
    # This migration is not easily reversible as it creates data
    # The previous migration's downgrade will handle removing the tables and columns
    # But we can't easily restore the pre-organization state
    print("Warning: This migration cannot be fully reversed. Organization data will be lost.")
    
    # Clear organization_id from all tables
    connection = op.get_bind()
    connection.execute(text("UPDATE credentials SET organization_id = NULL"))
    connection.execute(text("UPDATE instruction_sets SET organization_id = NULL"))
    connection.execute(text("UPDATE jobs SET organization_id = NULL"))
    connection.execute(text("UPDATE webhook_configs SET organization_id = NULL"))
    connection.execute(text("UPDATE dita_templates SET organization_id = NULL"))
    
    # Delete all organization data
    connection.execute(text("DELETE FROM organization_invitations"))
    connection.execute(text("DELETE FROM organization_members"))
    connection.execute(text("DELETE FROM organizations"))