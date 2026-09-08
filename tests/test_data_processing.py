import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.data_processing import (
    normalize_raw_observations, run_pipeline, detect_outliers_iqr,
    detect_outliers_mad, deduplicate, DataQualityStatus,
)


def _base_row(**overrides):
    row = dict(
        origin="DEL", destination="BOM", airline="IndiGo", flight_number="6E123",
        travel_date="2026-02-15", collection_timestamp="2026-02-01T00:00:00",
        booking_window_days=14, fare_class="ECONOMY_SAVER",
        base_fare=4000, taxes_fees=1200, total_fare=5200,
        currency="INR", availability_status="AVAILABLE",
        source=None, source_type=None,
        data_quality_status=np.nan, quality_flags=np.nan,
    )
    row.update(overrides)
    return row


class TestOutlierDetection(unittest.TestCase):
    def test_iqr_flags_extreme_value(self):
        s = pd.Series([5000, 5100, 5200, 4900, 5050, 5150, 35000])
        mask = detect_outliers_iqr(s)
        self.assertTrue(mask.iloc[-1])
        self.assertFalse(mask.iloc[0])

    def test_mad_flags_extreme_value(self):
        s = pd.Series([5000, 5100, 5200, 4900, 5050, 5150, 500])
        mask = detect_outliers_mad(s)
        self.assertTrue(mask.iloc[-1])

    def test_small_sample_no_false_positive(self):
        s = pd.Series([5000, 5200])
        self.assertFalse(detect_outliers_iqr(s).any())
        self.assertFalse(detect_outliers_mad(s).any())


class TestStructuralValidation(unittest.TestCase):
    def test_valid_row_passes(self):
        df = pd.DataFrame([_base_row()])
        norm = normalize_raw_observations(df, "DEMO_SIMULATED", "DEMO_SIMULATED")
        clean, report = run_pipeline(df, "DEMO_SIMULATED", "DEMO_SIMULATED")
        self.assertEqual(clean.iloc[0]["data_quality_status"], DataQualityStatus.VALID.value)

    def test_negative_fare_is_invalid(self):
        df = pd.DataFrame([_base_row(total_fare=-500, base_fare=-1000, taxes_fees=500)])
        clean, report = run_pipeline(df, "DEMO_SIMULATED", "DEMO_SIMULATED")
        self.assertEqual(clean.iloc[0]["data_quality_status"], DataQualityStatus.INVALID.value)

    def test_same_origin_destination_is_invalid(self):
        df = pd.DataFrame([_base_row(destination="DEL")])
        clean, report = run_pipeline(df, "DEMO_SIMULATED", "DEMO_SIMULATED")
        self.assertEqual(clean.iloc[0]["data_quality_status"], DataQualityStatus.INVALID.value)

    def test_cancelled_flight_is_unavailable(self):
        df = pd.DataFrame([_base_row(availability_status="CANCELLED")])
        clean, report = run_pipeline(df, "DEMO_SIMULATED", "DEMO_SIMULATED")
        self.assertEqual(clean.iloc[0]["data_quality_status"], DataQualityStatus.UNAVAILABLE.value)

    def test_missing_total_fare_is_invalid(self):
        df = pd.DataFrame([_base_row(total_fare=np.nan, base_fare=np.nan, taxes_fees=np.nan)])
        clean, report = run_pipeline(df, "DEMO_SIMULATED", "DEMO_SIMULATED")
        self.assertEqual(clean.iloc[0]["data_quality_status"], DataQualityStatus.INVALID.value)

    def test_implausibly_low_fare_is_invalid(self):
        df = pd.DataFrame([_base_row(total_fare=50, base_fare=30, taxes_fees=20)])
        clean, report = run_pipeline(df, "DEMO_SIMULATED", "DEMO_SIMULATED")
        self.assertEqual(clean.iloc[0]["data_quality_status"], DataQualityStatus.INVALID.value)


class TestDeduplication(unittest.TestCase):
    def test_exact_duplicate_removed(self):
        df = pd.DataFrame([_base_row(), _base_row()])
        norm = normalize_raw_observations(df, "DEMO_SIMULATED", "DEMO_SIMULATED")
        deduped, removed = deduplicate(norm)
        self.assertEqual(removed, 1)
        self.assertEqual(len(deduped), 1)

    def test_different_flights_not_deduped(self):
        df = pd.DataFrame([_base_row(), _base_row(flight_number="6E999", total_fare=5300)])
        norm = normalize_raw_observations(df, "DEMO_SIMULATED", "DEMO_SIMULATED")
        deduped, removed = deduplicate(norm)
        self.assertEqual(removed, 0)


class TestSourceLabeling(unittest.TestCase):
    def test_demo_rows_labelled_correctly(self):
        df = pd.DataFrame([_base_row()])
        clean, _ = run_pipeline(df, "DEMO_SIMULATED", "DEMO_SIMULATED")
        self.assertEqual(clean.iloc[0]["source"], "DEMO_SIMULATED")
        self.assertEqual(clean.iloc[0]["source_type"], "DEMO_SIMULATED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
