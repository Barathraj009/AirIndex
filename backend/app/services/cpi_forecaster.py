"""
AirIndex India — Holt-Winters CPI Airfare Forecaster
=====================================================
Forecasts the official MoSPI airfare CPI series (07.3.3.1) forward using
Holt's linear exponential smoothing with expanding uncertainty bands.

The output is a *statistical projection* derived from the observed series.
It is always labelled as a forecast and never merged with official data.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np


def _fit_holt(values: np.ndarray) -> tuple[float, float]:
    """Fit Holt's linear method (double exponential smoothing)."""
    alpha = 0.35
    beta = 0.15
    n = len(values)
    level = float(values[0])
    trend = float(values[1] - values[0]) if n > 1 else 0.0

    fitted = np.zeros(n)
    fitted[0] = level
    for i in range(1, n):
        y = float(values[i])
        prev_level = level
        fitted[i] = prev_level + trend
        level = alpha * y + (1 - alpha) * (prev_level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend

    residuals = values - fitted
    return level, trend


def forecast_cpi_series(
    series: List[Dict],
    forecast_steps: int = 6,
) -> Dict:
    """
    Given historical series [{"period": "2026-01", "airfare_index": 100.0}, ...],
    returns point forecasts with 80%/95% confidence bands.
    """
    valid_points = [
        p for p in series
        if p.get("airfare_index") is not None
    ]
    if len(valid_points) < 6:
        return {
            "available": False,
            "method": "HOLT_LINEAR",
            "note": "At least 6 historical periods are required for a reliable projection.",
            "forecast_points": [],
        }

    periods = [p["period"] for p in valid_points]
    values = np.array([float(p["airfare_index"]) for p in valid_points], dtype=float)

    level, trend = _fit_holt(values)

    n = len(values)
    residuals = values[1:] - values[:-1]  # one-step change residuals
    std_err = float(np.std(residuals))
    std_err = max(
        std_err,
        float(np.std(values) * 0.05),  # floor: 5% of series scale
    )

    last_year, last_month = map(int, periods[-1].split("-"))

    forecast_points = []
    for step in range(1, forecast_steps + 1):
        month = last_month + step
        year = last_year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        period_label = f"{year:04d}-{month:02d}"

        point_est = level + trend * step

        # Expanding uncertainty horizon (sqrt law) plus residual dispersion.
        horizon_factor = float(np.sqrt(step))
        ci_80_half = 1.282 * std_err * horizon_factor
        ci_95_half = 1.960 * std_err * horizon_factor

        forecast_points.append({
            "period": period_label,
            "forecast_value": round(float(point_est), 2),
            "lower_80": round(float(point_est - ci_80_half), 2),
            "upper_80": round(float(point_est + ci_80_half), 2),
            "lower_95": round(float(point_est - ci_95_half), 2),
            "upper_95": round(float(point_est + ci_95_half), 2),
            "trend_direction": (
                "UPWARD" if trend > 0.2 else
                ("DOWNWARD" if trend < -0.2 else "STABLE")
            ),
        })

    growth_pct = round(
        ((forecast_points[-1]["forecast_value"] - values[-1]) / values[-1]) * 100,
        2,
    )

    return {
        "available": True,
        "method": "HOLT_LINEAR",
        "historical_periods_used": n,
        "last_observed_period": periods[-1],
        "monthly_drift_rate": round(trend, 3),
        "projected_horizon_growth_pct": growth_pct,
        "forecast_points": forecast_points,
        "note": "Statistical projection from observed data. Not an official value.",
    }