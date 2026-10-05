"""users

Revision ID: c7e2a94d1b58
Revises: a3c91f0b7d24
Create Date: 2026-10-04 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e2a94d1b58'
down_revision: Union[str, Sequence[str], None] = 'a3c91f0b7d24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=160), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('picture', sa.String(length=400), nullable=True),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('broker_id', sa.Integer(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['broker_id'], ['brokers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('users')
