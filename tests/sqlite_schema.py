"""
SQLite translation of deployment/schema_postgres.sql
========================================================
PostgreSQL isn't available in this build sandbox, so this module exists
solely to verify the *design* of the schema (relationships, indexes,
constraint behaviour) against real seeded data using SQLite, which is
available. This is NOT what runs in production — Alembic against
PostgreSQL is (see deployment/schema_postgres.sql, the canonical DDL).

Differences from the Postgres DDL (SQLite has no SERIAL/JSONB/TIMESTAMPTZ):
  SERIAL      -> INTEGER PRIMARY KEY AUTOINCREMENT
  TIMESTAMPTZ -> TEXT (ISO8601)
  JSONB       -> TEXT (JSON-encoded)
  BOOLEAN     -> INTEGER (0/1)
Foreign key enforcement is off by default in SQLite and is turned on
explicitly below (`PRAGMA foreign_keys = ON`), matching Postgres's
always-on behaviour, so constraint violations are actually exercised.
"""

SQLITE_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    weight REAL NOT NULL,
    distance_tier TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE (origin, destination)
);

CREATE TABLE airlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    iata_code TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    base_url TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    min_delay_seconds REAL DEFAULT 5.0,
    last_success_at TEXT,
    last_failure_reason TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE ingestion_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_source_id INTEGER NOT NULL REFERENCES data_sources(id),
    triggered_by TEXT,
    started_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'RUNNING',
    rows_collected INTEGER DEFAULT 0,
    rows_valid INTEGER DEFAULT 0,
    rows_invalid INTEGER DEFAULT 0,
    rows_suspicious INTEGER DEFAULT 0,
    rows_unavailable INTEGER DEFAULT 0,
    error_message TEXT,
    raw_payload_path TEXT
);

CREATE TABLE fare_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id TEXT NOT NULL UNIQUE,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    airline TEXT NOT NULL,
    flight_number TEXT,
    travel_date TEXT NOT NULL,
    collection_timestamp TEXT NOT NULL,
    booking_window_days INTEGER,
    fare_class TEXT,
    base_fare REAL,
    taxes_fees REAL,
    total_fare REAL,
    currency TEXT DEFAULT 'INR',
    availability_status TEXT DEFAULT 'UNKNOWN',
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    data_quality_status TEXT NOT NULL,
    quality_flags TEXT,
    ingestion_run_id INTEGER REFERENCES ingestion_runs(id)
);
CREATE INDEX ix_route_period ON fare_observations (origin, destination, travel_date);
CREATE INDEX ix_route_window_period ON fare_observations (origin, destination, booking_window_days, travel_date);
CREATE INDEX ix_fare_source_type ON fare_observations (source_type);
CREATE INDEX ix_fare_quality_status ON fare_observations (data_quality_status);

CREATE TABLE index_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_period TEXT NOT NULL,
    methodology_version TEXT NOT NULL,
    booking_window_weights TEXT,
    include_suspicious INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    notes TEXT
);

CREATE TABLE index_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_config_id INTEGER NOT NULL REFERENCES index_configs(id),
    as_of_period TEXT NOT NULL,
    index_value REAL NOT NULL,
    change_from_base_pct REAL NOT NULL,
    n_observations_used INTEGER DEFAULT 0,
    routes_missing_data TEXT,
    calculation_breakdown TEXT,
    computed_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX ix_index_runs_period ON index_runs (as_of_period);

CREATE TABLE index_route_contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_run_id INTEGER NOT NULL REFERENCES index_runs(id),
    route TEXT NOT NULL,
    weight REAL NOT NULL,
    base_period_fare REAL,
    as_of_period_fare REAL,
    relative REAL,
    contribution_pct REAL NOT NULL
);
CREATE INDEX ix_route_contrib_run ON index_route_contributions (index_run_id);

CREATE TABLE index_airline_contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_run_id INTEGER NOT NULL REFERENCES index_runs(id),
    airline TEXT NOT NULL,
    contribution_pct REAL NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'VIEWER',
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    last_login_at TEXT
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    user_email TEXT,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    details TEXT,
    timestamp TEXT DEFAULT (datetime('now'))
);
CREATE INDEX ix_audit_log_timestamp ON audit_log (timestamp);
"""
