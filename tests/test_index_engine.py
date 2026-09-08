import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.index_engine import IndexConfig, compute_index, compute_index_series


def _synthetic_df():
    """A small, hand-built dataset with a known, verifiable answer:
    two routes, equal weights, DEL-BOM fares double in the as-of period,
    BLR-HYD fares stay flat -> index should be exactly 100 * (0.5*2.0 + 0.5*1.0) = 150.
    """
    rows = []
    for period, del_bom_fare, blr_hyd_fare in [("2026-01", 5000, 3000), ("2026-02", 10000, 3000)]:
        travel_date = f"{period}-10"
        for i in range(5):  # a few repeated obs so median is well-defined
            rows.append(dict(
                origin="DEL", destination="BOM", airline="IndiGo",
                travel_date=travel_date, booking_window_days=7,
                total_fare=del_bom_fare, data_quality_status="VALID",
            ))
            rows.append(dict(
                origin="BLR", destination="HYD", airline="Akasa Air",
                travel_date=travel_date, booking_window_days=7,
                total_fare=blr_hyd_fare, data_quality_status="VALID",
            ))
    return pd.DataFrame(rows)


class TestIndexEngine(unittest.TestCase):
    def test_known_answer(self):
        df = _synthetic_df()
        config = IndexConfig(base_period="2026-01", route_weights={"DEL-BOM": 0.5, "BLR-HYD": 0.5})
        result = compute_index(df, config, as_of_period="2026-02")
        self.assertAlmostEqual(result.index_value, 150.0, places=2)

    def test_base_period_equals_100(self):
        df = _synthetic_df()
        config = IndexConfig(base_period="2026-01", route_weights={"DEL-BOM": 0.5, "BLR-HYD": 0.5})
        result = compute_index(df, config, as_of_period="2026-01")
        self.assertAlmostEqual(result.index_value, 100.0, places=2)

    def test_reproducibility(self):
        df = _synthetic_df()
        config = IndexConfig(base_period="2026-01", route_weights={"DEL-BOM": 0.5, "BLR-HYD": 0.5})
        r1 = compute_index(df, config, as_of_period="2026-02")
        r2 = compute_index(df, config, as_of_period="2026-02")
        self.assertEqual(r1.as_dict(), r2.as_dict())

    def test_missing_route_is_excluded_and_reported(self):
        df = _synthetic_df()
        config = IndexConfig(
            base_period="2026-01",
            route_weights={"DEL-BOM": 0.5, "BLR-HYD": 0.3, "DEL-MAA": 0.2},  # DEL-MAA has no data
        )
        result = compute_index(df, config, as_of_period="2026-02")
        self.assertIn("DEL-MAA", result.routes_missing_data)
        # Weights renormalize across the two routes that DO have data:
        # DEL-BOM: 0.5/0.8=0.625 (relative 2.0), BLR-HYD: 0.3/0.8=0.375 (relative 1.0)
        # index = 100 * (0.625*2.0 + 0.375*1.0) = 162.5
        self.assertAlmostEqual(result.index_value, 162.5, places=2)

    def test_invalid_weights_raise(self):
        config = IndexConfig(base_period="2026-01", route_weights={"DEL-BOM": 0.3, "BLR-HYD": 0.3})
        with self.assertRaises(ValueError):
            compute_index(_synthetic_df(), config, as_of_period="2026-02")

    def test_series_handles_periods_with_no_data(self):
        df = _synthetic_df()
        config = IndexConfig(base_period="2026-01", route_weights={"DEL-BOM": 0.5, "BLR-HYD": 0.5})
        series = compute_index_series(df, config, ["2026-01", "2026-02", "2099-12"])
        self.assertIsNone(series[-1]["index_value"])
        self.assertEqual(series[-1]["n_observations_used"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
