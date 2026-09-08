import unittest
from app.services.cpi_engine import simulate_cpi_augmentation, HISTORICAL_MOSPI_CPI


class TestCpiEngine(unittest.TestCase):
    def test_cpi_simulation_basic(self):
        apix_series = {
            "2026-01": 100.0,
            "2026-02": 105.0,
            "2026-03": 110.0,
        }
        res = simulate_cpi_augmentation(apix_series)
        self.assertTrue(len(res.points) > 0)
        self.assertIn("airfare_weight_pct", res.as_dict())
        self.assertIn("mean_headline_delta_bps", res.as_dict())
        self.assertGreater(res.lag_reduction_days_est, 0)

    def test_cpi_custom_weights(self):
        apix_series = {"2026-01": 100.0, "2026-02": 120.0}
        res_standard = simulate_cpi_augmentation(apix_series, airfare_weight_in_cpi=0.002)
        res_higher = simulate_cpi_augmentation(apix_series, airfare_weight_in_cpi=0.01)
        self.assertGreater(res_higher.max_headline_delta_bps, res_standard.max_headline_delta_bps)


if __name__ == "__main__":
    unittest.main()
