"""Add max_tickets column to jobs table

Revision ID: add_max_tickets
Revises: 
Create Date: 2026-01-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_max_tickets'
down_revision = 'add_ai_credential_to_jobs'
branch_labels = None
depends_on = None


def upgrade():
    # Add max_tickets column to jobs table
    op.add_column('jobs', sa.Column('max_tickets', sa.Integer(), nullable=True))


def downgrade():
    # Remove max_tickets column from jobs table
    op.drop_column('jobs', 'max_tickets')