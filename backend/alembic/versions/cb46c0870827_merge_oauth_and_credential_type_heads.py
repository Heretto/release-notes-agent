"""merge_oauth_and_credential_type_heads

Revision ID: cb46c0870827
Revises: add_oauth_fields_to_users, migrate_credential_type_to_varchar
Create Date: 2026-06-23 17:02:49.500796

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb46c0870827'
down_revision: Union[str, None] = ('add_oauth_fields_to_users', 'migrate_credential_type_to_varchar')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
