"""Unit tests for app.core.json_safe: non-finite floats must never reach
the JSON layer (Postgres stores float8 NaN; stdlib json rejects it, which
broke GET /api/fares with HTTP 500 until fixed)."""

import unittest

from app.core.json_safe import json_safe_float, records_json_safe


class JsonSafeTestCase(unittest.TestCase):
    def test_nan_becomes_none(self):
        self.assertIsNone(json_safe_float(float("nan")))

    def test_inf_becomes_none(self):
        self.assertIsNone(json_safe_float(float("inf")))
        self.assertIsNone(json_safe_float(float("-inf")))

    def test_finite_floats_pass_through(self):
        self.assertEqual(json_safe_float(12.5), 12.5)
        self.assertEqual(json_safe_float(-0.0), -0.0)

    def test_non_float_values_untouched(self):
        self.assertIsNone(json_safe_float(None))
        self.assertEqual(json_safe_float(7), 7)
        self.assertEqual(json_safe_float("nan"), "nan")

    def test_records_rewrite_only_non_finite(self):
        rows = [
            {"total_fare": float("nan"), "origin": "DEL", "n": 1},
            {"total_fare": 3200.0, "origin": "BOM", "n": 2},
        ]
        out = records_json_safe(rows)
        self.assertIsNone(out[0]["total_fare"])
        self.assertEqual(out[0]["origin"], "DEL")
        self.assertEqual(out[1]["total_fare"], 3200.0)
        self.assertEqual(out[0]["n"], 1)
        self.assertEqual(out[1]["n"], 2)

    def test_records_returns_new_list(self):
        rows = [{"x": float("nan")}]
        out = records_json_safe(rows)
        self.assertIsNot(out, rows)
        self.assertIsNone(out[0]["x"])


if __name__ == "__main__":
    unittest.main()