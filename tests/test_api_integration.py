"""API integration tests — full request stack (FastAPI TestClient →
routers → services) against the real Postgres schema, executed via the
Alembic migration against the isolated `airindex_test` database.

These run automatically with:
    PYTHONPATH=.;./backend python -m unittest discover -s tests -v

They never touch the development `airindex` database: this module forces
DATABASE_URL to AIRINDEX_TEST_DB_URL and refuses to run against it.
"""

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

AIRINDEX_TEST_DB_URL = (
    "postgresql+psycopg2://airindex:airindex_dev_secret@localhost:5432/airindex_test"
)

# Must be set before any app import so get_settings() (lru_cached at first
# import) binds the engine/session to the test database, and so the
# scheduler stays disabled (environment=test).
os.environ["DATABASE_URL"] = AIRINDEX_TEST_DB_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET_KEY"] = "integration-test-secret-not-for-production"

sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import engine, SessionLocal  # noqa: E402
from app.models import Base  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _wipe_all_tables():
    db = SessionLocal()
    try:
        meta = Base.metadata
        # Drop children first: simplest reliable order is drop-all/recreate
        # on the test schema — fast enough for integration tests.
        meta.drop_all(bind=engine)
        meta.create_all(bind=engine)
    finally:
        db.close()


class APIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "airindex_test" not in engine.url.database:
            raise RuntimeError(
                "Refusing to seed integration data into non-test database "
                f"{engine.url.database!r}"
            )
        _wipe_all_tables()
        from scripts.seed_database import seed

        seed()

    def setUp(self):
        # Deterministic baseline: wipe + reseed before every test.
        _wipe_all_tables()
        from scripts.seed_database import seed

        seed()

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
        self.assertEqual(body["base_period"], "2026-01")
        # Base period index must be exactly 100.0
        r_base = client.get("/api/index/current?as_of_period=2026-01", headers=self._auth(token))
        self.assertEqual(r_base.json()["index_value"], 100.0)

    def test_index_trend_series(self):
        token = self._login()["access_token"]
        r = client.get("/api/index/trend?periods=2026-01,2026-04", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        series = r.json()["series"]
        self.assertEqual(len(series), 2)
        self.assertEqual(series[0]["period"], "2026-01")
        self.assertEqual(series[0]["index_value"], 100.0)

    def test_available_periods(self):
        token = self._login()["access_token"]
        r = client.get("/api/index/available-periods", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        self.assertIn("2026-01", r.json()["periods"])

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
        self.assertIn("IndiGo", names)

    # ---- data quality / fares ----

    def test_data_quality_summary_shape(self):
        token = self._login()["access_token"]
        r = client.get("/api/data-quality/summary", headers=self._auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        for key in ("total_rows", "valid", "suspicious", "invalid", "unavailable",
                    "valid_pct", "issues_sample"):
            self.assertIn(key, body)
        self.assertEqual(body["total_rows"], 7330)

    def test_fares_filters(self):
        token = self._login()["access_token"]
        r = client.get("/api/fares?origin=DEL&destination=BOM&limit=5", headers=self._auth(token))
        self.assertEqual(r.status_code, 200)
        rows = r.json()
        self.assertLessEqual(len(rows), 5)
        if rows:
            self.assertEqual(rows[0]["origin"], "DEL")
            self.assertEqual(rows[0]["destination"], "BOM")

    # ---- scraping / ingestion ----

    def test_scraping_trigger_and_runs(self):
        token = self._login()["access_token"]
        r = client.post("/api/scraping/trigger", headers=self._auth(token), json={"source_names": ["DEMO_GENERATOR"]})
        self.assertEqual(r.status_code, 200, r.text)
        runs = r.json()["runs"]
        self.assertEqual(runs[0]["status"], "SUCCESS")
        # deterministic demo data -> re-run inserts nothing new
        r2 = client.post("/api/scraping/trigger", headers=self._auth(token), json={"source_names": ["DEMO_GENERATOR"]})
        self.assertEqual(r2.json()["runs"][0]["rows_collected"], 0)

    # ---- backtesting ----

    def test_backtesting_reports_source_unavailable_honestly(self):
        """Period far outside any seeded reference data must report
        SOURCE UNAVAILABLE rather than fabricating comparison figures."""
        token = self._login()["access_token"]
        r = client.post("/api/backtesting/run", headers=self._auth(token),
                        json={"start_period": "2027-01", "end_period": "2027-06"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertFalse(body["reference_available"])
        self.assertIn("SOURCE UNAVAILABLE", body["note"])

    def test_backtesting_reports_seeded_reference(self):
        """Within the seeded DGCA reference window the comparison must
        come back available with metrics and aligned points."""
        token = self._login()["access_token"]
        r = client.post("/api/backtesting/run", headers=self._auth(token),
                        json={"start_period": "2026-02", "end_period": "2026-08"})
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
        # mount one route to have a real endpoint
        inner.add_route("/x", lambda request: JSONResponse({"ok": True}))
        with TC(app) as c:
            self.assertEqual(c.get("/x").status_code, 200)
            self.assertEqual(c.get("/x").status_code, 200)
            r = c.get("/x")
            self.assertEqual(r.status_code, 429)
            self.assertIn("Retry-After", r.headers)


if __name__ == "__main__":
    unittest.main(verbosity=2)