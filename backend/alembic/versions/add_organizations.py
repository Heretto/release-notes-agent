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
down_revision = 'initial_schema'
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

    # Create organization_members table
    op.create_table('organization_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(50), server_default='member'),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create organization_invitations table
    op.create_table('organization_invitations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), server_default='member'),
        sa.Column('token', sa.String(255), nullable=False),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )

    # Create instruction_sets table (jql_query added later by add_jql_to_instructions)
    op.create_table('instruction_sets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('user_instructions', sa.Text()),
        sa.Column('dita_template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('heretto_folder_id', sa.String(255)),
        sa.Column('publish_to_heretto', sa.Boolean(), server_default=sa.false()),
        sa.Column('is_default', sa.Boolean(), server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dita_template_id'], ['dita_templates.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create jobs table (ai_credential_id and max_tickets added by later migrations)
    op.create_table('jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('instruction_set_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('jql_query', sa.Text(), nullable=False),
        sa.Column('additional_instructions', sa.Text()),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('triggered_by', sa.String(20), nullable=False),
        sa.Column('output_filename', sa.String(255)),
        sa.Column('heretto_folder_id', sa.String(255)),
        sa.Column('auto_publish', sa.Boolean(), server_default=sa.false()),
        sa.Column('tickets_processed', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['instruction_set_id'], ['instruction_sets.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create job_artifacts table
    op.create_table('job_artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('artifact_type', sa.String(50), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('heretto_doc_id', sa.String(255)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create job_requests table
    op.create_table('job_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_type', sa.String(50), nullable=False),
        sa.Column('request_data', sa.Text()),
        sa.Column('response_data', sa.Text()),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text()),
        sa.Column('duration_ms', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create webhook_configs table (organization_id added later by add_org_id_to_webhook_configs)
    op.create_table('webhook_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('trigger_events', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('jql_filter', sa.Text()),
        sa.Column('instruction_set_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('auto_publish', sa.Boolean(), server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true()),
        sa.Column('secret_token', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['instruction_set_id'], ['instruction_sets.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop tables in reverse dependency order
    op.drop_table('webhook_configs')
    op.drop_table('job_requests')
    op.drop_table('job_artifacts')
    op.drop_table('jobs')
    op.drop_table('instruction_sets')
    op.drop_table('organization_invitations')
    op.drop_table('organization_members')

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