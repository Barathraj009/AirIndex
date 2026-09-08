import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.demo_data_generator import generate_demo_observations, ROUTE_BASKET
from app.services.data_processing import run_pipeline
from app.services.index_engine import IndexConfig, compute_index
from sqlite_schema import SQLITE_SCHEMA


def build_seeded_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SQLITE_SCHEMA)

    # --- reference data ---
    for route, (weight, base_fare, tier) in ROUTE_BASKET.items():
        origin, dest = route.split("-")
        conn.execute(
            "INSERT INTO routes (origin, destination, weight, distance_tier) VALUES (?,?,?,?)",
            (origin, dest, weight, tier),
        )
    conn.execute(
        "INSERT INTO data_sources (name, source_type, active) VALUES (?,?,?)",
        ("DEMO_GENERATOR", "DEMO_SIMULATED", 1),
    )
    source_id = conn.execute("SELECT id FROM data_sources WHERE name='DEMO_GENERATOR'").fetchone()[0]

    conn.execute(
        "INSERT INTO ingestion_runs (data_source_id, triggered_by, status, started_at, completed_at) "
        "VALUES (?,?,?,?,?)",
        (source_id, "test_harness", "SUCCESS", datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()),
    )
    run_id = conn.execute("SELECT id FROM ingestion_runs").fetchone()[0]

    # --- generate + process real fare data through the tested pipeline ---
    raw = generate_demo_observations(start_date=date(2026, 1, 1), n_months=3)
    clean_df, quality_report = run_pipeline(raw, source="DEMO_SIMULATED", source_type="DEMO_SIMULATED")

    rows = clean_df.to_dict("records")
    conn.executemany(
        """INSERT OR IGNORE INTO fare_observations
           (observation_id, origin, destination, airline, flight_number, travel_date,
            collection_timestamp, booking_window_days, fare_class, base_fare, taxes_fees,
            total_fare, currency, availability_status, source, source_type,
            data_quality_status, quality_flags, ingestion_run_id)
           VALUES (:observation_id,:origin,:destination,:airline,:flight_number,:travel_date,
                   :collection_timestamp,:booking_window_days,:fare_class,:base_fare,:taxes_fees,
                   :total_fare,:currency,:availability_status,:source,:source_type,
                   :data_quality_status,:quality_flags,:run_id)""",
        [{**r, "run_id": run_id} for r in rows],
    )

    # --- compute + persist an index run ---
    route_weights = {r: w for r, (w, _, _) in ROUTE_BASKET.items()}
    config = IndexConfig(base_period="2026-01", route_weights=route_weights)
    periods = sorted(clean_df["travel_date"].apply(lambda d: d[:7]).unique())
    result = compute_index(clean_df, config, as_of_period=periods[-1])

    conn.execute(
        "INSERT INTO index_configs (base_period, methodology_version, is_active) VALUES (?,?,?)",
        (config.base_period, config.methodology_version, 1),
    )
    config_id = conn.execute("SELECT id FROM index_configs").fetchone()[0]

    conn.execute(
        """INSERT INTO index_runs
           (index_config_id, as_of_period, index_value, change_from_base_pct,
            n_observations_used, routes_missing_data, calculation_breakdown)
           VALUES (?,?,?,?,?,?,?)""",
        (config_id, result.as_of_period, result.index_value, result.change_from_base_pct,
         result.n_observations_used, json.dumps(result.routes_missing_data),
         json.dumps(result.calculation_breakdown)),
    )
    index_run_id = conn.execute("SELECT id FROM index_runs").fetchone()[0]

    for route, contrib in result.route_contributions.items():
        rf = result.route_fares.get(route, {})
        conn.execute(
            """INSERT INTO index_route_contributions
               (index_run_id, route, weight, base_period_fare, as_of_period_fare, relative, contribution_pct)
               VALUES (?,?,?,?,?,?,?)""",
            (index_run_id, route, rf.get("weight"), rf.get("base_period_fare"),
             rf.get("as_of_period_fare"), rf.get("relative"), contrib),
        )

    conn.execute(
        "INSERT INTO users (email, hashed_password, role) VALUES (?,?,?)",
        ("admin@airindex.gov.in", "pbkdf2_sha256$1$aa$bb", "ADMIN"),
    )

    conn.commit()
    return conn, result, quality_report


class TestSQLiteSchemaDesign(unittest.TestCase):
    """These tests validate the *design* of the schema (relationships,
    the kinds of queries the dashboard API will run) against real
    pipeline output. Production uses PostgreSQL via SQLAlchemy/Alembic
    (deployment/schema_postgres.sql) — that layer isn't executable in
    this offline sandbox, so this is the closest available proof that
    the schema holds together end-to-end with real data."""

    @classmethod
    def setUpClass(cls):
        cls.conn, cls.index_result, cls.quality_report = build_seeded_db()

    def test_routes_seeded(self):
        n = self.conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
        self.assertEqual(n, len(ROUTE_BASKET))

    def test_fare_observations_loaded(self):
        n = self.conn.execute("SELECT COUNT(*) FROM fare_observations").fetchone()[0]
        self.assertGreater(n, 1000)

    def test_dashboard_summary_query(self):
        """Simulates the query /api/dashboard/summary would run: latest
        index run joined to its config."""
        row = self.conn.execute(
            """SELECT ir.index_value, ir.change_from_base_pct, ic.methodology_version
               FROM index_runs ir JOIN index_configs ic ON ir.index_config_id = ic.id
               ORDER BY ir.computed_at DESC LIMIT 1"""
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row[0], self.index_result.index_value, places=2)

    def test_route_contribution_query(self):
        """Simulates /api/analytics/route-contributions: top routes by
        contribution magnitude for the latest index run."""
        rows = self.conn.execute(
            """SELECT rc.route, rc.contribution_pct
               FROM index_route_contributions rc
               JOIN index_runs ir ON rc.index_run_id = ir.id
               ORDER BY ABS(rc.contribution_pct) DESC LIMIT 5"""
        ).fetchall()
        self.assertGreater(len(rows), 0)

    def test_data_quality_breakdown_query(self):
        """Simulates /api/data-quality/summary: counts by status."""
        rows = self.conn.execute(
            "SELECT data_quality_status, COUNT(*) FROM fare_observations GROUP BY data_quality_status"
        ).fetchall()
        status_counts = dict(rows)
        self.assertEqual(status_counts.get("VALID", 0), self.quality_report.valid)

    def test_airline_snapshot_query(self):
        """Simulates /api/airlines: median-ish fare per airline (SQLite
        has no MEDIAN, so this checks AVG as a structural proxy — the
        real FastAPI layer uses pandas median exactly as index_engine
        does)."""
        rows = self.conn.execute(
            """SELECT airline, COUNT(*), AVG(total_fare) FROM fare_observations
               WHERE data_quality_status='VALID' GROUP BY airline ORDER BY COUNT(*) DESC"""
        ).fetchall()
        self.assertEqual(len(rows), 5)  # 5 airlines in ROUTE_BASKET/AIRLINES

    def test_route_uniqueness_constraint_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO routes (origin, destination, weight) VALUES ('DEL','BOM',0.1)")

    def test_foreign_key_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO ingestion_runs (data_source_id, status) VALUES (9999, 'RUNNING')"
            )

    def test_observation_id_uniqueness_enforced(self):
        row = self.conn.execute("SELECT observation_id, origin FROM fare_observations LIMIT 1").fetchone()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO fare_observations (observation_id, origin, destination, airline, "
                "travel_date, collection_timestamp, source, source_type, data_quality_status) "
                "VALUES (?, 'XXX', 'YYY', 'Test', '2026-01-01', '2026-01-01T00:00:00', 'x', 'x', 'VALID')",
                (row[0],),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
