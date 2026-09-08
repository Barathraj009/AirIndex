import unittest
import pandas as pd
from app.services.cpi_engine import simulate_cpi_augmentation, HISTORICAL_MOSPI_CPI
from app.services.anomaly_detector import detect_fare_anomalies
from app.services.forecaster import forecast_index_series
from app.services.dgca_service import get_calibrated_route_weights, get_dgca_benchmark_series


class TestNewFeatures(unittest.TestCase):
    def test_cpi_augmentation(self):
        apix_series = {"2026-01": 100.0, "2026-02": 103.5, "2026-03": 108.2}
        res = simulate_cpi_augmentation(apix_series)
        self.assertEqual(len(res.points), 3)
        self.assertGreater(res.lag_reduction_days_est, 0)
        self.assertIn("APIx", res.policy_summary)

    def test_dgca_traffic_calibration(self):
        active_routes = ["DEL-BOM", "BOM-DEL", "DEL-BLR", "DEL-CCU"]
        weights = get_calibrated_route_weights(active_routes)
        self.assertEqual(len(weights), len(active_routes))
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=3)
        # DEL-BOM is highest traffic route
        self.assertGreater(weights["DEL-BOM"], weights["DEL-CCU"])

    def test_dgca_benchmark_series(self):
        bench = get_dgca_benchmark_series()
        self.assertIn("2026-01", bench)
        self.assertEqual(bench["2026-01"], 100.0)

    def test_forecasting_bounds(self):
        series = [
            {"period": "2026-01", "index_value": 100.0},
            {"period": "2026-02", "index_value": 102.0},
            {"period": "2026-03", "index_value": 104.5},
            {"period": "2026-04", "index_value": 107.0},
        ]
        fc = forecast_index_series(series, forecast_steps=3)
        self.assertTrue(fc["forecast_available"])
        self.assertEqual(len(fc["forecast_points"]), 3)
        for pt in fc["forecast_points"]:
            self.assertGreater(pt["upper_95"], pt["forecast_value"])
            self.assertLess(pt["lower_95"], pt["forecast_value"])

    def test_anomaly_detection_multi_route(self):
        df = pd.DataFrame([
            {"origin": "DEL", "destination": "BOM", "airline": "IndiGo", "travel_date": "2026-03-01",
             "booking_window_days": 15, "total_fare": 4500.0, "data_quality_status": "VALID"},
            {"origin": "DEL", "destination": "BOM", "airline": "Air India", "travel_date": "2026-03-01",
             "booking_window_days": 15, "total_fare": 4700.0, "data_quality_status": "VALID"},
            {"origin": "DEL", "destination": "BOM", "airline": "Akasa Air", "travel_date": "2026-03-01",
             "booking_window_days": 15, "total_fare": 4400.0, "data_quality_status": "VALID"},
            {"origin": "DEL", "destination": "BOM", "airline": "SpiceJet", "travel_date": "2026-03-01",
             "booking_window_days": 15, "total_fare": 4600.0, "data_quality_status": "VALID"},
            {"origin": "DEL", "destination": "BOM", "airline": "IndiGo", "travel_date": "2026-03-01",
             "booking_window_days": 15, "total_fare": 22000.0, "data_quality_status": "VALID"},
        ])
        anomalies = detect_fare_anomalies(df)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["route"], "DEL-BOM")
        self.assertGreater(anomalies[0]["deviation_pct"], 100)


if __name__ == "__main__":
    unittest.main()
