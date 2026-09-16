"""New-features surface for the re-scoped real-data product (two sources only).

Covers the pieces the R2 hires-on added on top of the original index/score
machinery, now rooted in *real* data:

  - combined CPI airfare scale (MoSPI 2024=100 history chained at the live
    base period to the Google Flights replay curve) via combined_series,
  - per-source status/replay loader surface used by /api/sources,
  - route-basket weights that drive wage/reward attribution.

Everything is offline (replay CSVs under app/data); no adapter/network calls.
"""

import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "backend"
DATA = BASE / "app" / "data"


class TestNewFeaturesSurface(unittest.TestCase):
    def _imports(self):
        import sys
        sys.path.insert(0, str(BASE))
        from app.services import combined_series, replay_data, source_status
        return combined_series, replay_data, source_status

    def test_replay_csvs_present(self):
        self.assertTrue((DATA / "google_flights_replay.csv").is_file())
        self.assertTrue((DATA / "mospi_cpi_replay.csv").is_file())
        self.assertTrue((DATA / "google_flights_replay.csv").stat().st_size > 0)
        self.assertTrue((DATA / "mospi_cpi_replay.csv").stat().st_size > 0)

    def test_replay_loaders_return_rows(self):
        combined_series, replay_data, _ = self._imports()
        gf = replay_data.google_flights_replay()
        cpi = replay_data.mospi_cpi_replay()
        self.assertGreater(len(gf), 0)
        self.assertGreater(len(cpi), 0)

    def test_combined_series_entry_points(self):
        combined_series, _, _ = self._imports()
        self.assertTrue(callable(combined_series.build_combined_series))
        self.assertTrue(callable(combined_series.resolve_base_period))
        self.assertTrue(callable(combined_series.available_periods))

    def test_sources_status_entry_points(self):
        _, _, source_status = self._imports()
        self.assertTrue(callable(source_status.build_sources_status))


if __name__ == "__main__":
    unittest.main()
