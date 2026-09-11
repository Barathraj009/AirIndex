"""add wpi_atf_index table

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-11

Adds the MoSPI WPI Aviation Turbine Fuel index table (item 1202010004,
base 2022-23=100) used for the "Fuel-cost vs Airfare" comparison.
Without this migration ``alembic check`` reports drift.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_add_wpi_atf_index"
down_revision = "0004_add_cpi_airfare_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wpi_atf_index",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("atf_index", sa.Float(), nullable=False),
        sa.Column("inflation_mom", sa.Float(), nullable=True),
        sa.Column("inflation_yoy", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("source_url", sa.String(length=200), nullable=True),
        sa.Column("wpi_code", sa.String(length=20), nullable=True),
        sa.Column("base_year", sa.String(length=10), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_wpi_atf_index_period",
        "wpi_atf_index",
        ["period"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_wpi_atf_index_period", table_name="wpi_atf_index")
    op.drop_table("wpi_atf_index")