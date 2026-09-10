"""add missing fare_observations composite indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-10

Adds the two composite indexes declared on FareObservation.__table_args__
but missing from the original 0001 migration. Without these, ``alembic
check`` reports drift on every run.
"""

from alembic import op

revision = "0003_add_obs_indexes"
down_revision = "0002_add_username"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_obs_airline_date",
        "fare_observations",
        ["airline", "travel_date"],
    )
    op.create_index(
        "ix_obs_window_quality",
        "fare_observations",
        ["booking_window_days", "data_quality_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_obs_window_quality", table_name="fare_observations")
    op.drop_index("ix_obs_airline_date", table_name="fare_observations")
