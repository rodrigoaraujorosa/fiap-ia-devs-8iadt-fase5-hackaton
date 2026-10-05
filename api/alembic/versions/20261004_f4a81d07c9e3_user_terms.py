"""user terms accepted

Revision ID: f4a81d07c9e3
Revises: e19b6f3a2c40
Create Date: 2026-10-04 23:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a81d07c9e3'
down_revision: Union[str, Sequence[str], None] = 'e19b6f3a2c40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'terms_accepted_at')
