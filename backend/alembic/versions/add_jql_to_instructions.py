"""Add JQL query field to instruction sets

Revision ID: add_jql_to_instructions
Revises: initial
Create Date: 2024-12-12
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_jql_to_instructions'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add jql_query column to instruction_sets table
    # First add it as nullable
    op.add_column('instruction_sets', 
        sa.Column('jql_query', sa.Text(), nullable=True)
    )
    
    # Set default value for existing rows
    op.execute(
        "UPDATE instruction_sets SET jql_query = 'project = DEMO ORDER BY created DESC' WHERE jql_query IS NULL"
    )
    
    # Now make it non-nullable
    op.alter_column('instruction_sets', 'jql_query', nullable=False)

def downgrade():
    op.drop_column('instruction_sets', 'jql_query')