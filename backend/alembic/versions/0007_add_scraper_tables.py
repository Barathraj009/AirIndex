"""add scraper_errors and fare_searches tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-13

Web-scraping framework (Phase 12): per-source error log and fare-search
audit tables. Maps to the existing schema:
  sources       -> data_sources
  scraper_runs  -> ingestion_runs
  fare_results  -> fare_observations
Without a migration these new models would report drift in
``alembic check`` against the existing head.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_add_scraper_tables"
down_revision = "0006_add_dgca_route_traffic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scraper_errors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("error_type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scraper_run_id", sa.Integer(), sa.ForeignKey("ingestion_runs.id"), nullable=True),
    )
    op.create_index("ix_scraper_errors_source_name", "scraper_errors", ["source_name"])

    op.create_table(
        "fare_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("origin", sa.String(length=3), nullable=False),
        sa.Column("destination", sa.String(length=3), nullable=False),
        sa.Column("travel_date", sa.String(length=10), nullable=True),
        sa.Column("booking_window_days", sa.Integer(), nullable=True),
        sa.Column("request_params", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rows_returned", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("searched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_fare_searches_source_name", "fare_searches", ["source_name"])


def downgrade() -> None:
    op.drop_index("ix_fare_searches_source_name", table_name="fare_searches")
    op.drop_table("fare_searches")
    op.drop_index("ix_scraper_errors_source_name", table_name="scraper_errors")
    op.drop_table("scraper_errors")