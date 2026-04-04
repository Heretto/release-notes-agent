"""Add id and invited_by columns to user_organizations table

Revision ID: add_id_to_user_organizations
Revises: migrate_existing_users_to_organizations
Create Date: 2026-03-07

Converts user_organizations from a composite-PK association table
to a full ORM model with a UUID primary key and invited_by tracking.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'add_id_to_user_organizations'
down_revision = 'add_max_tickets'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # Check if user_organizations table exists
    table_exists = connection.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'user_organizations'
        )
    """)).scalar()

    if not table_exists:
        # Table doesn't exist at all; create it with the full schema
        op.create_table(
            'user_organizations',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('role', sa.String(50), server_default='member'),
            sa.Column('invited_by', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
        )
        return

    # Check if 'id' column already exists
    id_exists = connection.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'user_organizations'
            AND column_name = 'id'
        )
    """)).scalar()

    if not id_exists:
        # Add the id column (nullable first so we can populate existing rows)
        op.add_column('user_organizations',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=True)
        )

        # Populate id for existing rows
        connection.execute(text("""
            UPDATE user_organizations SET id = gen_random_uuid() WHERE id IS NULL
        """))

        # Make id NOT NULL
        op.alter_column('user_organizations', 'id', nullable=False)

        # Drop the old composite primary key
        # The constraint name varies; find it dynamically
        pk_name = connection.execute(text("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'user_organizations'
            AND constraint_type = 'PRIMARY KEY'
        """)).scalar()

        if pk_name:
            op.drop_constraint(pk_name, 'user_organizations', type_='primary')

        # Add new primary key on id
        op.create_primary_key('pk_user_organizations', 'user_organizations', ['id'])

    # Check if 'invited_by' column already exists
    invited_by_exists = connection.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'user_organizations'
            AND column_name = 'invited_by'
        )
    """)).scalar()

    if not invited_by_exists:
        op.add_column('user_organizations',
            sa.Column('invited_by', postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.create_foreign_key(
            'fk_user_organizations_invited_by',
            'user_organizations', 'users',
            ['invited_by'], ['id'],
            ondelete='SET NULL'
        )

    # If organization_members table exists (from a previous migration variant),
    # migrate any data that isn't already in user_organizations
    org_members_exists = connection.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'organization_members'
        )
    """)).scalar()

    if org_members_exists:
        # Check if organization_members has invited_by column
        om_has_invited_by = connection.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'organization_members'
                AND column_name = 'invited_by'
            )
        """)).scalar()

        if om_has_invited_by:
            connection.execute(text("""
                INSERT INTO user_organizations (id, user_id, organization_id, role, invited_by, joined_at)
                SELECT om.id, om.user_id, om.organization_id, om.role, om.invited_by, om.joined_at
                FROM organization_members om
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_organizations uo
                    WHERE uo.user_id = om.user_id
                    AND uo.organization_id = om.organization_id
                )
            """))
        else:
            connection.execute(text("""
                INSERT INTO user_organizations (id, user_id, organization_id, role, joined_at)
                SELECT om.id, om.user_id, om.organization_id, om.role, om.joined_at
                FROM organization_members om
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_organizations uo
                    WHERE uo.user_id = om.user_id
                    AND uo.organization_id = om.organization_id
                )
            """))


def downgrade():
    connection = op.get_bind()

    # Check if invited_by exists before dropping
    invited_by_exists = connection.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'user_organizations'
            AND column_name = 'invited_by'
        )
    """)).scalar()

    if invited_by_exists:
        op.drop_constraint('fk_user_organizations_invited_by', 'user_organizations', type_='foreignkey')
        op.drop_column('user_organizations', 'invited_by')

    # Check if id column exists
    id_exists = connection.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = 'user_organizations'
            AND column_name = 'id'
        )
    """)).scalar()

    if id_exists:
        # Drop the id-based primary key
        op.drop_constraint('pk_user_organizations', 'user_organizations', type_='primary')

        # Restore composite primary key
        op.create_primary_key(
            'user_organizations_pkey', 'user_organizations',
            ['user_id', 'organization_id']
        )

        op.drop_column('user_organizations', 'id')
