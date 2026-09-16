"""Real-data smoke tests for the two-source AirIndex backend. Phase 4 demo
scaffolding, the WPI-ATF fuel backdrop, DGCA city-pair traffic, and the 11-
scraper framework were removed in the real-data re-scope. The product graph is
built from exactly two live sources: Google Flights fare observations (replayed
from the bundled CSV) chained to the official MoSPI CPI airfare index.

These tests exercise the replay-data loaders and the combined-series builder
that produce the graph the frontend draws."""

import unittest

from app.services.replay_data import google_flights_replay, mospi_cpi_replay
from app.services.route_basket import ROUTE_BASKET
from app.services.combined_series import resolve_base_period, build_combined_series


class TestReplayData(unittest.TestCase):
    def test_google_replay_is_two_source_google(self):
        rows = google_flights_replay()
        self.assertTrue(len(rows) >= 10)
        sources = {r["source"] for r in rows}
        self.assertEqual(sources, {"GOOGLE_FLIGHTS_API"})

    def test_mospi_cpi_replay_is_mospi(self):
        rows = mospi_cpi_replay()
        self.assertTrue(len(rows) >= 12)
        for r in rows:
            self.assertEqual(r["source"], "MOSPI_CPI")
            self.assertEqual(r["cpi_code"], "07.3.3.1")

    def test_route_basket_weights_sum_to_one(self):
        total = sum(w for _, (w, _) in ROUTE_BASKET.items())
        self.assertAlmostEqual(total, 1.0, places=6)
        self.assertEqual(len(ROUTE_BASKET), 16)

    def test_resolve_base_period_demo(self):
        self.assertEqual(resolve_base_period("2025-01", {"2025-01", "2025-02"}), "2025-01")


if __name__ == "__main__":
    unittest.main()
