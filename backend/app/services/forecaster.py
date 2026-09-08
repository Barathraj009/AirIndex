"""
AirIndex India — Time-Series Forecaster
========================================
Forecasts future APIx trajectory (1-3 months forward) using
exponential smoothing & trend extrapolation with statistical confidence intervals.
"""

from __future__ import annotations

from typing import List, Dict, Optional
import numpy as np


def forecast_index_series(series: List[Dict], forecast_steps: int = 3) -> Dict:
    """
    Given historical series [{"period": "2026-01", "index_value": 100.0}, ...],
    computes point forecasts and confidence bands for forward periods.
    """
    valid_points = [p for p in series if p.get("index_value") is not None]
    if len(valid_points) < 2:
        return {
            "forecast_available": False,
            "note": "At least 2 historical periods required for statistical forecasting.",
            "forecast_points": [],
        }

    periods = [p["period"] for p in valid_points]
    values = np.array([float(p["index_value"]) for p in valid_points], dtype=float)

    # Linear / Holt trend estimation
    n = len(values)
    x = np.arange(n)
    slope, intercept = np.polyfit(x, values, 1)

    residuals = values - (intercept + slope * x)
    std_err = float(np.std(residuals)) if len(residuals) > 2 else float(np.std(values) * 0.5)
    std_err = max(std_err, 1.2)  # minimum sensible standard error for index levels

    # Parse last period (YYYY-MM)
    last_period = periods[-1]
    last_year, last_month = map(int, last_period.split("-"))

    forecast_points = []
    for step in range(1, forecast_steps + 1):
        month = last_month + step
        year = last_year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        period_label = f"{year:04d}-{month:02d}"

        future_x = n - 1 + step
        point_est = float(intercept + slope * future_x)

        # Expanding uncertainty horizon
        horizon_factor = np.sqrt(step)
        ci_80_half = 1.282 * std_err * horizon_factor
        ci_95_half = 1.960 * std_err * horizon_factor

        forecast_points.append({
            "period": period_label,
            "forecast_value": round(point_est, 2),
            "lower_80": round(point_est - ci_80_half, 2),
            "upper_80": round(point_est + ci_80_half, 2),
            "lower_95": round(point_est - ci_95_half, 2),
            "upper_95": round(point_est + ci_95_half, 2),
            "trend_direction": "UPWARD" if slope > 0.3 else ("DOWNWARD" if slope < -0.3 else "STABLE"),
        })

    growth_rate_pct = round(((forecast_points[-1]["forecast_value"] - values[-1]) / values[-1]) * 100, 2)

    return {
        "forecast_available": True,
        "historical_periods_used": len(values),
        "monthly_drift_rate": round(float(slope), 3),
        "projected_horizon_growth_pct": growth_rate_pct,
        "forecast_points": forecast_points,
    }
