"""add cpi_airfare_index table

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-10

Adds the MoSPI CPI airfare index table (code 07.3.3.1, base 2024=100)
which is the PRIMARY data source. Without this migration ``alembic check``
reports drift.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_add_cpi_airfare_index"
down_revision = "0003_add_obs_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cpi_airfare_index",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("airfare_index", sa.Float(), nullable=False),
        sa.Column("transport_index", sa.Float(), nullable=True),
        sa.Column("general_index", sa.Float(), nullable=True),
        sa.Column("inflation_yoy", sa.Float(), nullable=True),
        sa.Column("inflation_mom", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("source_url", sa.String(length=200), nullable=True),
        sa.Column("cpi_code", sa.String(length=20), nullable=True),
        sa.Column("base_year", sa.String(length=10), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_cpi_airfare_index_period",
        "cpi_airfare_index",
        ["period"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_cpi_airfare_index_period", table_name="cpi_airfare_index")
    op.drop_table("cpi_airfare_index")