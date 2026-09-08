import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.backtesting import compute_metrics, align_series, run_backtest


class TestBacktestingMetrics(unittest.TestCase):
    def test_perfect_match_zero_error(self):
        m = compute_metrics([100, 101, 102], [100, 101, 102])
        self.assertEqual(m["mae"], 0.0)
        self.assertEqual(m["rmse"], 0.0)
        self.assertEqual(m["correlation"], 1.0)

    def test_known_mae_rmse(self):
        # actual - reference = [2, -2, 2] -> MAE = 2, RMSE = 2
        m = compute_metrics([102, 98, 102], [100, 100, 100])
        self.assertAlmostEqual(m["mae"], 2.0)
        self.assertAlmostEqual(m["rmse"], 2.0)

    def test_mape_known_value(self):
        # |110-100|/100 = 0.10 -> 10%
        m = compute_metrics([110, 110], [100, 100])
        self.assertAlmostEqual(m["mape"], 10.0)

    def test_insufficient_points_returns_none(self):
        m = compute_metrics([100], [100])
        self.assertIsNone(m["mae"])

    def test_align_series_only_uses_overlap(self):
        actual = {"2026-01": 100, "2026-02": 101, "2026-03": 102}
        reference = {"2026-02": 100.5, "2026-03": 101.8, "2026-04": 103}
        periods, a, r = align_series(actual, reference)
        self.assertEqual(periods, ["2026-02", "2026-03"])
        self.assertEqual(a, [101, 102])

    def test_run_backtest_no_reference_reports_unavailable(self):
        result = run_backtest({"2026-01": 100}, {})
        self.assertFalse(result["reference_available"])
        self.assertEqual(result["points"], [])
        self.assertIsNone(result["mae"])

    def test_run_backtest_no_overlap_reports_unavailable(self):
        result = run_backtest({"2026-01": 100}, {"2099-12": 100})
        self.assertFalse(result["reference_available"])

    def test_run_backtest_with_real_overlap(self):
        actual = {"2026-01": 100, "2026-02": 103, "2026-03": 105}
        reference = {"2026-01": 100, "2026-02": 102, "2026-03": 104}
        result = run_backtest(actual, reference)
        self.assertTrue(result["reference_available"])
        self.assertEqual(len(result["points"]), 3)
        self.assertIsNotNone(result["mae"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
