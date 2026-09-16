"""drop unused source tables (demo/scraper/wpi-atf/dgca)

Revision ID: 0008_drop_unused_source_tables
Revises: 0007_add_scraper_tables
Create Date: 2026-09-16

The product now serves exactly two real data sources (GOOGLE_FLIGHTS_API and
MOSPI_CPI) and two database tables that hold their records:

* ``fare_observations``  — live Google Flights observations (GOOGLE_FLIGHTS_API)
* ``cpi_airfare_index``  — official MoSPI CPI airfare index (07.3.3.1)

The remaining scraper/demo/web tables are no longer part of the product and are
dropped here together with their supporting indexes:

* ``scraper_errors`` / ``fare_searches``   (old 11-scraper framework, 0007)
* ``wpi_atf_index``                        (WPI ATF fuel backdrop, 0005)
* ``dgca_route_traffic``                   (DGCA route traffic backdrop, 0006)

``cpi_airfare_index`` (0004) is intentionally kept — it is the official
history that anchors the combined airfare index. Its now-unserved columns
(transport_index / general_index) remain so older dashboards don't need to be
re-created; the API no longer exposes them.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_drop_unused_source_tables"
down_revision = "0007_add_scraper_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_scraper_errors_source_name", table_name="scraper_errors")
    op.drop_table("scraper_errors")
    op.drop_index("ix_fare_searches_source_name", table_name="fare_searches")
    op.drop_table("fare_searches")
    op.drop_table("wpi_atf_index")
    op.drop_table("dgca_route_traffic")


def downgrade() -> None:
    # --- dgca_route_traffic (0006) ---
    op.create_table(
        "dgca_route_traffic",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("route_key", sa.String(length=7), nullable=False),
        sa.Column("origin", sa.String(length=3), nullable=False),
        sa.Column("destination", sa.String(length=3), nullable=False),
        sa.Column("passengers", sa.Float(), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("data_source_id", sa.Integer(),
                  sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("source_url", sa.String(length=255), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dgca_route_traffic_period", "dgca_route_traffic", ["period"])

    # --- wpi_atf_index (0005) ---
    op.create_table(
        "wpi_atf_index",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period", sa.String(length=7), nullable=False, unique=True),
        sa.Column("data_date", sa.Date(), nullable=False),
        sa.Column("atf_index", sa.Float(), nullable=False),
        sa.Column("wpi_index", sa.Float(), nullable=True),
        sa.Column("inflation_yoy", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=50), default="MOSPI_WPI"),
        sa.Column("source_url", sa.String(length=255), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # --- scraper tables (0007) ---
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
    op.create_table(
        "scraper_errors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("error_type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scraper_run_id", sa.Integer(),
                  sa.ForeignKey("ingestion_runs.id"), nullable=True),
    )
    op.create_index("ix_scraper_errors_source_name", "scraper_errors", ["source_name"])