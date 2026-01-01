"""Add ai_credential_id to jobs table

Revision ID: add_ai_credential_to_jobs
Revises: 
Create Date: 2025-12-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_ai_credential_to_jobs'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add ai_credential_id column to jobs table
    op.add_column('jobs', 
        sa.Column('ai_credential_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_jobs_ai_credential_id',
        'jobs', 
        'credentials',
        ['ai_credential_id'], 
        ['id']
    )

def downgrade():
    # Remove foreign key constraint
    op.drop_constraint('fk_jobs_ai_credential_id', 'jobs', type_='foreignkey')
    
    # Remove column
    op.drop_column('jobs', 'ai_credential_id')