"""add username column to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '0002_add_username'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username', sa.String(100), nullable=True, unique=True, index=True))


def downgrade() -> None:
    op.drop_column('users', 'username')
