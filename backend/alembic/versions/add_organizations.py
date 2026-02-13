"""Add organizations and update credentials for organization-wide access

Revision ID: add_organizations
Revises: 
Create Date: 2024-01-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_organizations'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create organizations table
    op.create_table('organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    
    # Create user_organizations association table
    op.create_table('user_organizations',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(50), default='member'),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'organization_id')
    )
    
    # Add current_organization_id to users table
    op.add_column('users', sa.Column('current_organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_users_current_org', 'users', 'organizations', ['current_organization_id'], ['id'])
    
    # Add organization_id and created_by to credentials table
    op.add_column('credentials', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('credentials', sa.Column('created_by', sa.String(255), nullable=True))
    
    # Create a default organization for existing data
    op.execute("""
        INSERT INTO organizations (id, name, slug, is_active)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Default Organization', 'default', true)
    """)
    
    # Associate all existing users with the default organization
    op.execute("""
        INSERT INTO user_organizations (user_id, organization_id, role)
        SELECT id, '00000000-0000-0000-0000-000000000001', 'member'
        FROM users
    """)
    
    # Update existing users to have the default organization as current
    op.execute("""
        UPDATE users 
        SET current_organization_id = '00000000-0000-0000-0000-000000000001'
    """)
    
    # Update existing credentials to belong to the default organization
    op.execute("""
        UPDATE credentials 
        SET organization_id = '00000000-0000-0000-0000-000000000001',
            created_by = (SELECT email FROM users WHERE users.id = credentials.user_id)
    """)
    
    # Now make organization_id NOT NULL
    op.alter_column('credentials', 'organization_id', nullable=False)
    
    # Add foreign key constraint
    op.create_foreign_key('fk_credentials_org', 'credentials', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    
    # Make user_id nullable (since credentials are org-owned, not user-owned)
    op.alter_column('credentials', 'user_id', nullable=True)


def downgrade():
    # Remove foreign key constraints
    op.drop_constraint('fk_credentials_org', 'credentials', type_='foreignkey')
    op.drop_constraint('fk_users_current_org', 'users', type_='foreignkey')
    
    # Make user_id NOT NULL again
    op.alter_column('credentials', 'user_id', nullable=False)
    
    # Remove columns
    op.drop_column('credentials', 'created_by')
    op.drop_column('credentials', 'organization_id')
    op.drop_column('users', 'current_organization_id')
    
    # Drop tables
    op.drop_table('user_organizations')
    op.drop_table('organizations')