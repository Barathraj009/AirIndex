"""DB schema contract for the re-scoped two-source product (backend-only green).

As of migration 0008 the AirIndex India schema is exactly the tables the two
live sources need:

  * ``cpi_airfare_index``   — MoSPI CPI airfare index (07.3.3.1, 2024=100)
  * ``fare_observations``   — Google Flights fare observations (replayed here,
                              but produced live by the gds_adapter in prod)
  * ``ingestion_runs``      — orchestration metadata for both sources
  * ``routes`` / ``route_basket`` / ``index_runs`` + contributions
No WPI-ATF, no DGCA, no scraper tables remain.
"""

import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "backend"


class TestSchemaContract(unittest.TestCase):
    def test_core_tables_present(self):
        import sys
        sys.path.insert(0, str(BASE))
        from app.models import Base
        names = set(Base.metadata.tables)
        for t in ("cpi_airfare_index", "fare_observations", "ingestion_runs",
                  "routes", "index_runs", "index_configs"):
            self.assertIn(t, names, f"missing required table: {t}")

    def test_legacy_tables_absent(self):
        import sys
        sys.path.insert(0, str(BASE))
        from app.models import Base
        names = set(Base.metadata.tables)
        for t in ("wpi_atf_index", "dgca_route_traffic", "scraper_errors",
                  "fare_searches", "scraper_runs"):
            self.assertNotIn(t, names, f"legacy table still present: {t}")

    def test_cpi_airfare_model_columns(self):
        import sys
        sys.path.insert(0, str(BASE))
        from app.models.cpi import CpiAirfareIndex
        cols = {c.name for c in CpiAirfareIndex.__table__.columns}
        self.assertTrue({"period", "airfare_index", "inflation_yoy",
                         "source", "base_year"} <= cols)

    def test_alembic_head_applies_offline(self):
        """The full 0001..0008 chain applies cleanly to a scratch SQLite DB."""
        import os
        import sys
        import tempfile
        import subprocess
        sys.path.insert(0, str(BASE))
        sqlite_path = os.path.join(tempfile.gettempdir(), "airindex_migrate_check.db")
        if os.path.exists(sqlite_path):
            os.remove(sqlite_path)
        env = dict(os.environ, DATABASE_URL=f"sqlite:///{sqlite_path}")
        r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                           cwd=str(BASE), env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
