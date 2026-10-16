"""Add the app role: author or reviewer

hop-core owns organization_members.role (ADMIN/MEMBER) as a Postgres enum on its own table,
and this app must not migrate hop-core's schema — so "may this person write release notes,
or only review them?" is answered on a table of ours instead. The two are orthogonal: an
org admin is an author, and a reviewer can hold either org role.

Keyed by email rather than user id so an admin can set the role of someone they are
inviting, before that person has an account: email is what the invitation addresses, so the
role is waiting when they accept.

**Every existing member is backfilled as an author.** Without that, turning this on would
make everyone a reviewer at the next request — including whoever deployed it — and nobody
would be able to promote anyone back.

NOTE: revision IDs must stay <= 32 characters — alembic_version.version_num is
VARCHAR(32), and a longer ID fails the version-table write *after* the DDL runs.

NOTE: the table is guarded. It is a brand-new ORM table, so create_all() at backend startup
may already have built it; see AGENTS.md on create_all() running on every start.

Revision ID: add_app_user_roles
Revises: add_comment_resolved
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_app_user_roles'
down_revision = 'add_comment_resolved'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if 'app_user_roles' not in inspector.get_table_names():
        op.create_table(
            'app_user_roles',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('set_by_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['set_by_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('organization_id', 'email', name='uq_app_user_role_email'),
        )
        op.create_index(
            op.f('ix_app_user_roles_organization_id'), 'app_user_roles', ['organization_id']
        )

    # Everyone already here keeps the access they have. Only accounts created after this
    # point start as reviewers. ON CONFLICT so re-running over a part-populated table is
    # safe, and lower() because the role lookup compares lower-cased addresses.
    op.execute("""
        INSERT INTO app_user_roles (id, organization_id, email, role, created_at)
        SELECT gen_random_uuid(), m.organization_id, lower(u.email), 'author', now()
        FROM organization_members m
        JOIN users u ON u.id = m.user_id
        ON CONFLICT ON CONSTRAINT uq_app_user_role_email DO NOTHING
    """)


def downgrade():
    op.drop_table('app_user_roles')
