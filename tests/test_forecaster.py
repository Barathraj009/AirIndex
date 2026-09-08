import unittest
from app.services.forecaster import forecast_index_series


class TestForecaster(unittest.TestCase):
    def test_forecast_basic(self):
        series = [
            {"period": "2026-01", "index_value": 100.0},
            {"period": "2026-02", "index_value": 102.5},
            {"period": "2026-03", "index_value": 105.0},
        ]
        res = forecast_index_series(series, forecast_steps=3)
        self.assertTrue(res["forecast_available"])
        self.assertEqual(len(res["forecast_points"]), 3)
        self.assertEqual(res["forecast_points"][0]["period"], "2026-04")
        self.assertGreater(res["forecast_points"][0]["upper_95"], res["forecast_points"][0]["forecast_value"])
        self.assertLess(res["forecast_points"][0]["lower_95"], res["forecast_points"][0]["forecast_value"])

    def test_forecast_insufficient_data(self):
        series = [{"period": "2026-01", "index_value": 100.0}]
        res = forecast_index_series(series)
        self.assertFalse(res["forecast_available"])


if __name__ == "__main__":
    unittest.main()
