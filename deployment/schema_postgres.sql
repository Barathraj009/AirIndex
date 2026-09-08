-- AirIndex India — PostgreSQL schema (reference copy — SUPERSEDED)
-- The source of truth is the Alembic baseline migration:
--   backend/alembic/versions/0001_initial_schema.py
-- which is generated from backend/app/models/*.py and verified drift-free
-- via `alembic check` (2026-09 rebuild). The SQL below is an earlier
-- hand-written draft and DIFFERS from the baseline (e.g. separate
-- non-default index names, observation_id as a unique constraint instead
-- of a unique index, missing reference_data_points). Do NOT hand-apply
-- it; use `alembic upgrade head`.

CREATE TABLE routes (
    id SERIAL PRIMARY KEY,
    origin VARCHAR(3) NOT NULL,
    destination VARCHAR(3) NOT NULL,
    weight DOUBLE PRECISION NOT NULL,
    distance_tier VARCHAR(20),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (origin, destination)
);

CREATE TABLE airlines (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    iata_code VARCHAR(2),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    source_type VARCHAR(30) NOT NULL,
    base_url VARCHAR(255),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    min_delay_seconds DOUBLE PRECISION DEFAULT 5.0,
    last_success_at TIMESTAMPTZ,
    last_failure_reason VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE booking_window_configs (
    id SERIAL PRIMARY KEY,
    days INTEGER NOT NULL UNIQUE,
    weight DOUBLE PRECISION NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE ingestion_runs (
    id SERIAL PRIMARY KEY,
    data_source_id INTEGER NOT NULL REFERENCES data_sources(id),
    triggered_by VARCHAR(100),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    rows_collected INTEGER DEFAULT 0,
    rows_valid INTEGER DEFAULT 0,
    rows_invalid INTEGER DEFAULT 0,
    rows_suspicious INTEGER DEFAULT 0,
    rows_unavailable INTEGER DEFAULT 0,
    error_message TEXT,
    raw_payload_path VARCHAR(255)
);

CREATE TABLE fare_observations (
    id SERIAL PRIMARY KEY,
    observation_id VARCHAR(16) NOT NULL UNIQUE,
    origin VARCHAR(3) NOT NULL,
    destination VARCHAR(3) NOT NULL,
    airline VARCHAR(100) NOT NULL,
    flight_number VARCHAR(20),
    travel_date DATE NOT NULL,
    collection_timestamp TIMESTAMPTZ NOT NULL,
    booking_window_days INTEGER,
    fare_class VARCHAR(30),
    base_fare DOUBLE PRECISION,
    taxes_fees DOUBLE PRECISION,
    total_fare DOUBLE PRECISION,
    currency VARCHAR(3) DEFAULT 'INR',
    availability_status VARCHAR(20) DEFAULT 'UNKNOWN',
    source VARCHAR(100) NOT NULL,
    source_type VARCHAR(30) NOT NULL,
    data_quality_status VARCHAR(20) NOT NULL,
    quality_flags VARCHAR(500),
    ingestion_run_id INTEGER REFERENCES ingestion_runs(id)
);
CREATE INDEX ix_route_period ON fare_observations (origin, destination, travel_date);
CREATE INDEX ix_route_window_period ON fare_observations (origin, destination, booking_window_days, travel_date);
CREATE INDEX ix_fare_source_type ON fare_observations (source_type);
CREATE INDEX ix_fare_quality_status ON fare_observations (data_quality_status);

CREATE TABLE index_configs (
    id SERIAL PRIMARY KEY,
    base_period VARCHAR(7) NOT NULL,
    methodology_version VARCHAR(30) NOT NULL,
    booking_window_weights JSONB,
    include_suspicious BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes TEXT
);

CREATE TABLE index_runs (
    id SERIAL PRIMARY KEY,
    index_config_id INTEGER NOT NULL REFERENCES index_configs(id),
    as_of_period VARCHAR(7) NOT NULL,
    index_value DOUBLE PRECISION NOT NULL,
    change_from_base_pct DOUBLE PRECISION NOT NULL,
    n_observations_used INTEGER DEFAULT 0,
    routes_missing_data JSONB,
    calculation_breakdown JSONB,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_index_runs_period ON index_runs (as_of_period);

CREATE TABLE index_route_contributions (
    id SERIAL PRIMARY KEY,
    index_run_id INTEGER NOT NULL REFERENCES index_runs(id),
    route VARCHAR(10) NOT NULL,
    weight DOUBLE PRECISION NOT NULL,
    base_period_fare DOUBLE PRECISION,
    as_of_period_fare DOUBLE PRECISION,
    relative DOUBLE PRECISION,
    contribution_pct DOUBLE PRECISION NOT NULL
);
CREATE INDEX ix_route_contrib_run ON index_route_contributions (index_run_id);

CREATE TABLE index_airline_contributions (
    id SERIAL PRIMARY KEY,
    index_run_id INTEGER NOT NULL REFERENCES index_runs(id),
    airline VARCHAR(100) NOT NULL,
    contribution_pct DOUBLE PRECISION NOT NULL
);
CREATE INDEX ix_airline_contrib_run ON index_airline_contributions (index_run_id);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'VIEWER',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    user_email VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(50),
    details JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_log_timestamp ON audit_log (timestamp);
