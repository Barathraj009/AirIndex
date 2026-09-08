"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-05

Baseline for the AirIndex India schema.

NOTE (2026-09-05): this file was originally hand-written against the
SQLAlchemy models before SQLAlchemy was installable, then REVISED after a
real `alembic revision --autogenerate` run on a fresh postgres 16.8
database confirmed drift: the hand-written version used non-default index
names (e.g. `ix_fare_airline` vs the SQLAlchemy-generated
`ix_fare_observations_airline`), built `observation_id` as a unique
constraint + separate non-unique index instead of the model's unique
index, and omitted the `ix_users_email` unique index. The body below IS
the fresh autogenerate output, so `alembic check`/subsequent
`--autogenerate` runs against this baseline report no drift.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "airlines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("iata_code", sa.String(length=2), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "booking_window_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("days"),
    )
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("min_delay_seconds", sa.Float(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "index_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_period", sa.String(length=7), nullable=False),
        sa.Column("methodology_version", sa.String(length=30), nullable=False),
        sa.Column("booking_window_weights", sa.JSON(), nullable=True),
        sa.Column("include_suspicious", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "reference_data_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_name", sa.String(length=50), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reference_data_points_dataset_name"),
        "reference_data_points",
        ["dataset_name"],
        unique=False,
    )
    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=3), nullable=False),
        sa.Column("destination", sa.String(length=3), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("distance_tier", sa.String(length=20), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("origin", "destination", name="uq_route_pair"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.String(length=50), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_log_timestamp"), "audit_log", ["timestamp"], unique=False
    )
    op.create_table(
        "index_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("index_config_id", sa.Integer(), nullable=False),
        sa.Column("as_of_period", sa.String(length=7), nullable=False),
        sa.Column("index_value", sa.Float(), nullable=False),
        sa.Column("change_from_base_pct", sa.Float(), nullable=False),
        sa.Column("n_observations_used", sa.Integer(), nullable=True),
        sa.Column("routes_missing_data", sa.JSON(), nullable=True),
        sa.Column("calculation_breakdown", sa.JSON(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["index_config_id"], ["index_configs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_index_runs_as_of_period"), "index_runs", ["as_of_period"], unique=False
    )
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data_source_id", sa.Integer(), nullable=False),
        sa.Column("triggered_by", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("rows_collected", sa.Integer(), nullable=True),
        sa.Column("rows_valid", sa.Integer(), nullable=True),
        sa.Column("rows_invalid", sa.Integer(), nullable=True),
        sa.Column("rows_suspicious", sa.Integer(), nullable=True),
        sa.Column("rows_unavailable", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_payload_path", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "fare_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("observation_id", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=3), nullable=False),
        sa.Column("destination", sa.String(length=3), nullable=False),
        sa.Column("airline", sa.String(length=100), nullable=False),
        sa.Column("flight_number", sa.String(length=20), nullable=True),
        sa.Column("travel_date", sa.Date(), nullable=False),
        sa.Column("collection_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booking_window_days", sa.Integer(), nullable=True),
        sa.Column("fare_class", sa.String(length=30), nullable=True),
        sa.Column("base_fare", sa.Float(), nullable=True),
        sa.Column("taxes_fees", sa.Float(), nullable=True),
        sa.Column("total_fare", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("availability_status", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("data_quality_status", sa.String(length=20), nullable=False),
        sa.Column("quality_flags", sa.String(length=500), nullable=True),
        sa.Column("ingestion_run_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fare_observations_airline"), "fare_observations", ["airline"], unique=False
    )
    op.create_index(
        op.f("ix_fare_observations_booking_window_days"),
        "fare_observations",
        ["booking_window_days"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fare_observations_data_quality_status"),
        "fare_observations",
        ["data_quality_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fare_observations_destination"),
        "fare_observations",
        ["destination"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fare_observations_observation_id"),
        "fare_observations",
        ["observation_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_fare_observations_origin"), "fare_observations", ["origin"], unique=False
    )
    op.create_index(
        op.f("ix_fare_observations_source_type"),
        "fare_observations",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fare_observations_travel_date"),
        "fare_observations",
        ["travel_date"],
        unique=False,
    )
    op.create_index(
        "ix_route_period", "fare_observations", ["origin", "destination", "travel_date"], unique=False
    )
    op.create_index(
        "ix_route_window_period",
        "fare_observations",
        ["origin", "destination", "booking_window_days", "travel_date"],
        unique=False,
    )
    op.create_table(
        "index_airline_contributions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("index_run_id", sa.Integer(), nullable=False),
        sa.Column("airline", sa.String(length=100), nullable=False),
        sa.Column("contribution_pct", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["index_run_id"], ["index_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_index_airline_contributions_index_run_id"),
        "index_airline_contributions",
        ["index_run_id"],
        unique=False,
    )
    op.create_table(
        "index_route_contributions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("index_run_id", sa.Integer(), nullable=False),
        sa.Column("route", sa.String(length=10), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("base_period_fare", sa.Float(), nullable=True),
        sa.Column("as_of_period_fare", sa.Float(), nullable=True),
        sa.Column("relative", sa.Float(), nullable=True),
        sa.Column("contribution_pct", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["index_run_id"], ["index_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_index_route_contributions_index_run_id"),
        "index_route_contributions",
        ["index_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_index_route_contributions_index_run_id"),
        table_name="index_route_contributions",
    )
    op.drop_table("index_route_contributions")
    op.drop_index(
        op.f("ix_index_airline_contributions_index_run_id"),
        table_name="index_airline_contributions",
    )
    op.drop_table("index_airline_contributions")
    op.drop_index("ix_route_window_period", table_name="fare_observations")
    op.drop_index("ix_route_period", table_name="fare_observations")
    op.drop_index(op.f("ix_fare_observations_travel_date"), table_name="fare_observations")
    op.drop_index(op.f("ix_fare_observations_source_type"), table_name="fare_observations")
    op.drop_index(op.f("ix_fare_observations_origin"), table_name="fare_observations")
    op.drop_index(op.f("ix_fare_observations_observation_id"), table_name="fare_observations")
    op.drop_index(op.f("ix_fare_observations_destination"), table_name="fare_observations")
    op.drop_index(
        op.f("ix_fare_observations_data_quality_status"), table_name="fare_observations"
    )
    op.drop_index(
        op.f("ix_fare_observations_booking_window_days"), table_name="fare_observations"
    )
    op.drop_index(op.f("ix_fare_observations_airline"), table_name="fare_observations")
    op.drop_table("fare_observations")
    op.drop_table("ingestion_runs")
    op.drop_index(op.f("ix_index_runs_as_of_period"), table_name="index_runs")
    op.drop_table("index_runs")
    op.drop_index(op.f("ix_audit_log_timestamp"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("routes")
    op.drop_index(
        op.f("ix_reference_data_points_dataset_name"), table_name="reference_data_points"
    )
    op.drop_table("reference_data_points")
    op.drop_table("index_configs")
    op.drop_table("data_sources")
    op.drop_table("booking_window_configs")
    op.drop_table("airlines")