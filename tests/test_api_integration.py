"""API integration tests - full request stack (FastAPI TestClient → routers →
services) against a real SQLite database seeded from the bundled replay CSVs
and the canonical route basket (no network, no Postgres required).

These run with:
    PYTHONPATH=.;./backend python -m unittest discover -s tests -v

The two real product sources are seeded: GOOGLE_FLIGHTS_API (30 fare
observations replayed from app/data/google_flights_replay.csv, periods
2026-09/2026-10, airline MULTI) and MOSPI_CPI (32 months of official CPI
airfare 07.3.3.1 from app/data/mospi_cpi_replay.csv, 2024=100 base).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Bind the app to a scratch SQLite database before any app import so
# get_settings() (lru_cached at first import) and the engine resolve to it.
_TMP_DB = tempfile.mktemp(suffix="_airindex_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.replace(os.sep, '/')}"
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET_KEY"] = "integration-test-secret-not-for-production"

sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import engine, SessionLocal  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.observations import FareObservation  # noqa: E402
from app.models.cpi import CpiAirfareIndex  # noqa: E402
from app.models.backtesting import ReferenceDataPoint  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _wipe_all_tables():
    db = SessionLocal()
    try:
        meta = Base.metadata
        meta.drop_all(bind=engine)
        meta.create_all(bind=engine)
    finally:
        db.close()


def _seed_real_data():
    """Seed routes + two sources + users + replay observations + CPI history
    + reference data, all from the bundled replay CSVs / canonical basket."""
    from scripts.seed_database import seed

    seed()

    db = SessionLocal()
    try:
        # Official MoSPI CPI airfare history (32 months, 2024=100).
        from app.services.replay_data import mospi_cpi_replay

        if db.query(CpiAirfareIndex).count() == 0:
            from datetime import date, datetime, timezone
            for r in mospi_cpi_replay():
                db.add(CpiAirfareIndex(
                    period=r["period"],
                    data_date=date.fromisoformat(r["period"] + "-15"),
                    airfare_index=float(r["airfare_index"]),
                    transport_index=float(r["transport_index"]) if r.get("transport_index") else None,
                    general_index=float(r["general_index"]) if r.get("general_index") else None,
                    inflation_yoy=float(r["inflation_yoy"]) if r.get("inflation_yoy") else None,
                    source=r.get("source", "MOSPI_CPI"),
                    source_url=r.get("source_url"),
                    cpi_code=r.get("cpi_code", "07.3.3.1"),
                    base_year=r.get("base_year", "2024=100"),
                    fetched_at=datetime.now(timezone.utc),
                    created_at=datetime.now(timezone.utc),
                ))
            db.commit()
            print(f"Seeded {db.query(CpiAirfareIndex).count()} CPI airfare index rows.")

        # Reference dataset the backtesting suite compares APIx against.
        if db.query(ReferenceDataPoint).count() == 0:
            last = (db.query(CpiAirfareIndex)
                    .order_by(CpiAirfareIndex.period.desc()).all())
            vals = {r.period: r.airfare_index for r in last[-2:]}
            for period in ("2026-09", "2026-10"):
                db.add(ReferenceDataPoint(
                    dataset_name="CPI_REFERENCE",
                    period=period,
                    value=vals.get(period, 135.0),
                    label="ALL_INDIA_AVG",
                ))
            db.commit()
            print(f"Seeded {db.query(ReferenceDataPoint).count()} reference data points.")
    finally:
        db.close()


class APIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _wipe_all_tables()
        _seed_real_data()

    def setUp(self):
        _wipe_all_tables()
        _seed_real_data()

    def _login(self, email="admin@airindex.gov.in", password="change-me-immediately"):
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)
        return body

    def _auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ---- auth ----

    def test_login_rejects_bad_credentials(self):
        r = client.post("/api/auth/login", json={"email": "admin@airindex.gov.in", "password": "wrong"})
        self.assertEqual(r.status_code, 401)

    def test_me_returns_user(self):
        token = self._login()["access_token"]
        r = client.get("/api/auth/me", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["email"], "admin@airindex.gov.in")
        self.assertEqual(r.json()["role"], "ADMIN")

    def test_unauthenticated_request_is_rejected(self):
        r = client.get("/api/dashboard/summary")
        self.assertEqual(r.status_code, 401)

    def test_login_requires_valid_email(self):
        r = client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"})
        self.assertEqual(r.status_code, 422)

    # ---- dashboard / index ----

    def test_dashboard_summary_returns_index(self):
        token = self._login()["access_token"]
        r = client.get("/api/dashboard/summary", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("index", body)
        self.assertIn("index_value", body["index"])

    def test_index_current_base_period_is_100(self):
        token = self._login()["access_token"]
        r = client.get("/api/index/current", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["base_period"], "2026-09")
        # Base period index must be exactly 100.0 (replay calendar window).
        r_base = client.get("/api/index/current?as_of_period=2026-09", headers=self._auth(token))
        self.assertEqual(r_base.status_code, 200, r_base.text)
        self.assertEqual(r_base.json()["index_value"], 100.0)

    def test_index_trend_series(self):
        token = self._login()["access_token"]
        r = client.get("/api/index/trend?periods=2026-09,2026-10", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        series = r.json()["series"]
        self.assertEqual(len(series), 2)
        self.assertEqual(series[0]["period"], "2026-09")
        self.assertEqual(series[0]["index_value"], 100.0)

    def test_available_periods(self):
        token = self._login()["access_token"]
        r = client.get("/api/index/available-periods", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        self.assertIn("2026-09", r.json()["periods"])

    # ---- reference / routes ----

    def test_routes_listed(self):
        token = self._login()["access_token"]
        r = client.get("/api/routes", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        routes = r.json()
        self.assertEqual(len(routes), 16)
        weights = sum(x["weight"] for x in routes)
        self.assertAlmostEqual(weights, 1.0, places=3)

    def test_route_duplicate_is_conflict(self):
        token = self._login()["access_token"]
        r = client.post("/api/routes", headers=self._auth(token),
                        json={"origin": "DEL", "destination": "BOM", "weight": 0.1})
        self.assertEqual(r.status_code, 409)

    def test_route_weight_update(self):
        token = self._login()["access_token"]
        r = client.patch("/api/routes/1/weight", headers=self._auth(token), json={"weight": 0.2})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertAlmostEqual(r.json()["weight"], 0.2)

    def test_airlines_listed(self):
        token = self._login()["access_token"]
        r = client.get("/api/airlines", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        names = {a["name"] for a in r.json()}
        self.assertIn("MULTI", names)

    # ---- data quality / fares ----

    def test_data_quality_summary_shape(self):
        token = self._login()["access_token"]
        r = client.get("/api/data-quality/summary", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        for key in ("total_rows", "valid", "suspicious", "invalid", "unavailable",
                    "valid_pct", "issues_sample"):
            self.assertIn(key, body)
        self.assertEqual(body["total_rows"], 30)

    def test_fares_filters(self):
        token = self._login()["access_token"]
        r = client.get("/api/fares?origin=DEL&destination=BOM&limit=5", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        rows = r.json()
        self.assertLessEqual(len(rows), 5)
        if rows:
            self.assertEqual(rows[0]["origin"], "DEL")
            self.assertEqual(rows[0]["destination"], "BOM")

    def test_fares_routes_summarized(self):
        token = self._login()["access_token"]
        r = client.get("/api/fares/routes", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        rows = r.json()
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)
        for row in rows:
            for key in ("route", "origin", "destination", "n", "n_valid",
                        "avg_fare", "min_fare", "max_fare", "latest_collected"):
                self.assertIn(key, row)
            self.assertGreaterEqual(row["n_valid"], 1)
            self.assertIsNotNone(row["avg_fare"])

    def test_fares_latest_returns_observations(self):
        token = self._login()["access_token"]
        r = client.get("/api/fares/latest", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        rows = r.json()
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)
        for row in rows[:5]:
            for key in ("origin", "destination", "travel_date", "total_fare",
                        "source", "source_type"):
                self.assertIn(key, row)

    def test_fares_latest_filters_dates_and_orders_ascending(self):
        """from_date must restrict travel dates >= start day."""
        token = self._login()["access_token"]
        rows = client.get("/api/fares/latest", headers=self._auth(token)).json()
        dates = [str(r["travel_date"]) for r in rows]
        ordered = all(left <= right for left, right in zip(dates, dates[1:]))
        self.assertTrue(ordered, "rows must be ordered by travel_date ascending")

        cutoff = min(dates)
        r = client.get(f"/api/fares/latest?from_date={cutoff}", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        sub_dates = {str(x["travel_date"]) for x in r.json()}
        self.assertEqual(sub_dates, set(dates))
        self.assertTrue(all(d >= cutoff for d in sub_dates))

        # A later cutoff (e.g. the second date) must drop only earlier dates.
        unique_dates = sorted(set(dates))
        later = unique_dates[1] if len(unique_dates) > 1 else unique_dates[0]
        r = client.get(f"/api/fares/latest?from_date={later}", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        sub_dates = {str(x["travel_date"]) for x in r.json()}
        self.assertTrue(all(d >= later for d in sub_dates))
        if len(unique_dates) > 1:
            self.assertNotIn(unique_dates[0], sub_dates)

    def test_fares_latest_rejects_bad_from_date(self):
        token = self._login()["access_token"]
        r = client.get("/api/fares/latest?from_date=not-a-date", headers=self._auth(token))
        self.assertEqual(r.status_code, 400)

    def test_bootstrap_replay_backfills_missing_departure_dates(self):
        """Deleting replay rows for a departure date must be healed by a
        re-run of _load_google_flights_replay (additive only, idempotent)."""
        from datetime import date

        from scripts.bootstrap_reference import _load_google_flights_replay

        db = SessionLocal()
        try:
            target = date(2026, 9, 17)
            gone = db.query(FareObservation).filter(FareObservation.travel_date == target).all()
            self.assertGreater(len(gone), 0, "expected replay rows to exist for the target date")
            target_keys = {(g.origin, g.destination, g.airline) for g in gone}
            for g in gone:
                db.delete(g)
            db.commit()
            self.assertEqual(
                db.query(FareObservation).filter(FareObservation.travel_date == target).count(), 0
            )

            _load_google_flights_replay(db)

            healed = db.query(FareObservation).filter(FareObservation.travel_date == target).all()
            self.assertEqual(len(healed), len(gone))
            self.assertEqual({(h.origin, h.destination, h.airline) for h in healed}, target_keys)

            total = db.query(FareObservation).count()
            _load_google_flights_replay(db)  # must be a no-op second run
            self.assertEqual(db.query(FareObservation).count(), total)
        finally:
            db.close()

    # ---- sources (two-source monitor, replaces scrapers monitor) ----

    def test_sources_lists_the_two_real_sources(self):
        token = self._login()["access_token"]
        r = client.get("/api/sources", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        names = {s["source_name"] for s in body["sources"]}
        self.assertEqual(names, {"GOOGLE_FLIGHTS_API", "MOSPI_CPI"})

    def test_sources_runs_is_a_list(self):
        token = self._login()["access_token"]
        r = client.get("/api/sources/runs?limit=10", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsInstance(r.json(), list)

    # ---- backtesting ----

    def test_backtesting_reports_source_unavailable_honestly(self):
        """Period far outside any reference data must report
        SOURCE UNAVAILABLE rather than fabricating comparison figures."""
        token = self._login()["access_token"]
        r = client.post("/api/backtesting/run", headers=self._auth(token),
                        json={"start_period": "2027-01", "end_period": "2027-06"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertFalse(body["reference_available"])
        self.assertIn("SOURCE UNAVAILABLE", body["note"])

    def test_backtesting_uses_seeded_reference(self):
        """Within the seeded CPI_REFERENCE window the comparison must come
        back available with aligned points."""
        token = self._login()["access_token"]
        r = client.post("/api/backtesting/run", headers=self._auth(token),
                        json={"start_period": "2026-09", "end_period": "2026-10",
                              "reference_dataset": "CPI_REFERENCE"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["reference_available"])
        self.assertGreater(len(body["points"]), 0)

    # ---- admin / exports ----

    def test_admin_audit_log_records_threshold(self):
        token = self._login()["access_token"]
        client.patch("/api/routes/1/weight", headers=self._auth(token), json={"weight": 0.2})
        r = client.get("/api/admin/audit-log", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        actions = {row["action"] for row in r.json()}
        self.assertIn("UPDATE_ROUTE_WEIGHT", actions)

    def test_exports_csv(self):
        token = self._login()["access_token"]
        r = client.get("/api/exports/fares.csv", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers["content-type"])
        self.assertIn("observation_id", r.text.split("\n")[0])


class RateLimitMiddlewareTests(unittest.TestCase):
    """Unit-level check of the in-memory limiter: 3rd request within the
    window is rejected with 429 + Retry-After."""

    def test_limit_enforced(self):
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from fastapi.testclient import TestClient as TC
        from app.core.rate_limit import RateLimitMiddleware

        inner = Starlette()
        app = RateLimitMiddleware(inner, limit_per_minute=2)
        inner.add_route("/x", lambda request: JSONResponse({"ok": True}))
        with TC(app) as c:
            self.assertEqual(c.get("/x").status_code, 200)
            self.assertEqual(c.get("/x").status_code, 200)
            r = c.get("/x")
            self.assertEqual(r.status_code, 429)
            self.assertIn("Retry-After", r.headers)


if __name__ == "__main__":
    unittest.main(verbosity=2)