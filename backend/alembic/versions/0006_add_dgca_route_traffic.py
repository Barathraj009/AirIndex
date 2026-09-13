"""add dgca_route_traffic table

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-11

Adds the DGCA directional city-pair passenger traffic table used to
calibrate route basket weights from official data. Without this migration
``alembic check`` reports drift against the DgcaTrafficRecord model.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_add_dgca_route_traffic"
down_revision = "0005_add_wpi_atf_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dgca_route_traffic",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("origin", sa.String(length=3), nullable=False),
        sa.Column("destination", sa.String(length=3), nullable=False),
        sa.Column("route_key", sa.String(length=7), nullable=False),
        sa.Column("passengers", sa.Float(), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("source_url", sa.String(length=255), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_dgca_route_traffic_route_key",
        "dgca_route_traffic",
        ["route_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_dgca_route_traffic_route_key", table_name="dgca_route_traffic")
    op.drop_table("dgca_route_traffic")