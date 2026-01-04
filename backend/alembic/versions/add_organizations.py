"""Add organizations for multi-tenancy support

Revision ID: add_organizations
Revises: add_max_tickets
Create Date: 2026-01-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision = 'add_organizations'
down_revision = 'add_max_tickets'
branch_labels = None
depends_on = None


def upgrade():
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('slug', sa.String(255), nullable=False, unique=True),
        sa.Column('settings', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
    )
    
    # Create index on slug for faster lookups
    op.create_index('ix_organizations_name', 'organizations', ['name'])
    op.create_index('ix_organizations_slug', 'organizations', ['slug'])
    
    # Create organization_members table
    op.create_table(
        'organization_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.Enum('admin', 'member', name='organizationrole'), nullable=False, server_default='member'),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id']),
        sa.UniqueConstraint('organization_id', 'user_id', name='unique_org_member')
    )
    
    # Create organization_invitations table
    op.create_table(
        'organization_invitations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'member', name='organizationrole'), nullable=False, server_default='member'),
        sa.Column('token', sa.String(255), nullable=False, unique=True),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'])
    )
    
    # Create index on invitation token for faster lookups
    op.create_index('ix_organization_invitations_token', 'organization_invitations', ['token'])
    
    # Add organization_id to existing tables (nullable for migration)
    op.add_column('credentials', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('instruction_sets', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('jobs', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('webhook_configs', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('dita_templates', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Add foreign key constraints for organization_id
    op.create_foreign_key('fk_credentials_organization', 'credentials', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_instruction_sets_organization', 'instruction_sets', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_jobs_organization', 'jobs', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_webhook_configs_organization', 'webhook_configs', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_dita_templates_organization', 'dita_templates', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    
    # Create indexes for organization_id for faster queries
    op.create_index('ix_credentials_organization_id', 'credentials', ['organization_id'])
    op.create_index('ix_instruction_sets_organization_id', 'instruction_sets', ['organization_id'])
    op.create_index('ix_jobs_organization_id', 'jobs', ['organization_id'])
    op.create_index('ix_webhook_configs_organization_id', 'webhook_configs', ['organization_id'])
    op.create_index('ix_dita_templates_organization_id', 'dita_templates', ['organization_id'])


def downgrade():
    # Drop indexes on organization_id columns
    op.drop_index('ix_dita_templates_organization_id', 'dita_templates')
    op.drop_index('ix_webhook_configs_organization_id', 'webhook_configs')
    op.drop_index('ix_jobs_organization_id', 'jobs')
    op.drop_index('ix_instruction_sets_organization_id', 'instruction_sets')
    op.drop_index('ix_credentials_organization_id', 'credentials')
    
    # Drop foreign key constraints
    op.drop_constraint('fk_dita_templates_organization', 'dita_templates', type_='foreignkey')
    op.drop_constraint('fk_webhook_configs_organization', 'webhook_configs', type_='foreignkey')
    op.drop_constraint('fk_jobs_organization', 'jobs', type_='foreignkey')
    op.drop_constraint('fk_instruction_sets_organization', 'instruction_sets', type_='foreignkey')
    op.drop_constraint('fk_credentials_organization', 'credentials', type_='foreignkey')
    
    # Drop organization_id columns from existing tables
    op.drop_column('dita_templates', 'organization_id')
    op.drop_column('webhook_configs', 'organization_id')
    op.drop_column('jobs', 'organization_id')
    op.drop_column('instruction_sets', 'organization_id')
    op.drop_column('credentials', 'organization_id')
    
    # Drop organization tables
    op.drop_index('ix_organization_invitations_token', 'organization_invitations')
    op.drop_table('organization_invitations')
    op.drop_table('organization_members')
    
    # Drop indexes and the organizations table
    op.drop_index('ix_organizations_slug', 'organizations')
    op.drop_index('ix_organizations_name', 'organizations')
    op.drop_table('organizations')
    
    # Drop the enum type
    op.execute('DROP TYPE IF EXISTS organizationrole')