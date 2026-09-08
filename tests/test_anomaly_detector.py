import unittest
import pandas as pd
from app.services.anomaly_detector import detect_fare_anomalies


class TestAnomalyDetector(unittest.TestCase):
    def test_empty_dataframe(self):
        df = pd.DataFrame()
        anomalies = detect_fare_anomalies(df)
        self.assertEqual(anomalies, [])

    def test_detect_surge_spike(self):
        # Create normal fares around 5000 and one massive spike at 18000
        records = [
            {"origin": "DEL", "destination": "BOM", "airline": "IndiGo", "travel_date": "2026-03-15",
             "booking_window_days": 15, "total_fare": 4800.0, "data_quality_status": "VALID"}
            for _ in range(10)
        ]
        records.append({
            "origin": "DEL", "destination": "BOM", "airline": "IndiGo", "travel_date": "2026-03-15",
            "booking_window_days": 15, "total_fare": 18500.0, "data_quality_status": "VALID"
        })
        df = pd.DataFrame(records)
        anomalies = detect_fare_anomalies(df)
        self.assertTrue(len(anomalies) > 0)
        self.assertEqual(anomalies[0]["route"], "DEL-BOM")
        self.assertEqual(anomalies[0]["severity"], "HIGH")


if __name__ == "__main__":
    unittest.main()
