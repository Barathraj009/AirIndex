"""
AirIndex India — Backtesting metrics
=======================================
Computes standard forecast-accuracy metrics comparing the calculated
APIx against a reference series (e.g. DGCA monthly average fares, once
an analyst sources that data, or an explicitly-labelled demonstration
dataset). Per spec section 8: never fabricate DGCA/historical results —
if no reference data exists for the requested period, the caller must
report `reference_available: False` rather than inventing numbers. This
module only computes metrics on whatever aligned pairs are actually
provided; it has no knowledge of where the data came from.
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def align_series(actual: dict, reference: dict) -> tuple[list, list, list]:
    """actual/reference: {period_label: value}. Returns
    (periods_used, actual_values, reference_values) — only periods
    present (and non-null) in both."""
    periods = sorted(p for p in actual if p in reference and actual[p] is not None and reference[p] is not None)
    a = [actual[p] for p in periods]
    r = [reference[p] for p in periods]
    return periods, a, r


def compute_metrics(actual: list, reference: list) -> dict:
    if len(actual) < 2:
        return {"mae": None, "rmse": None, "mape": None, "correlation": None,
                "note": "fewer than 2 aligned periods; metrics undefined"}

    a = np.array(actual, dtype=float)
    r = np.array(reference, dtype=float)

    mae = float(np.mean(np.abs(a - r)))
    rmse = float(np.sqrt(np.mean((a - r) ** 2)))
    mape = float(np.mean(np.abs((a - r) / r)) * 100) if np.all(r != 0) else None

    if np.std(a) == 0 or np.std(r) == 0:
        correlation = None  # undefined for a constant series
    else:
        correlation = float(stats.pearsonr(a, r)[0])

    return {"mae": round(mae, 4), "rmse": round(rmse, 4),
            "mape": round(mape, 4) if mape is not None else None,
            "correlation": round(correlation, 4) if correlation is not None else None}


def run_backtest(actual_series: dict, reference_series: dict) -> dict:
    """actual_series/reference_series: {period_label: value}.
    Returns a full result dict including the aligned points (for
    charting) and an explicit `reference_available` flag."""
    if not reference_series:
        return {
            "reference_available": False,
            "note": "No reference dataset available for the requested period/dataset. "
                    "Showing SOURCE UNAVAILABLE rather than fabricated comparison data.",
            "points": [], "mae": None, "rmse": None, "mape": None, "correlation": None,
        }

    periods, a, r = align_series(actual_series, reference_series)
    if not periods:
        return {
            "reference_available": False,
            "note": "Reference dataset exists but has no overlapping periods with the requested range.",
            "points": [], "mae": None, "rmse": None, "mape": None, "correlation": None,
        }

    metrics = compute_metrics(a, r)
    points = [{"period": p, "actual": av, "reference": rv} for p, av, rv in zip(periods, a, r)]
    return {"reference_available": True, "points": points, **metrics}
