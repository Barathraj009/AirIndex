"""
AirIndex India — Airfare Price Index Engine (APIx)
=====================================================
Computes a weighted airfare price index from validated fare observations
(status == VALID or SUSPICIOUS-but-included, per config).

Methodology (v1.0.0) — "Modified Laspeyres Route-Weighted Index"
------------------------------------------------------------------
1. For each (route, booking_window) cell, compute the *representative
   fare* for a period as the median of total_fare across all VALID
   observations in that cell during the period. Median is used instead
   of mean because airfare distributions are right-skewed and median is
   robust to any residual outliers.

2. For each route, aggregate across its configured booking windows using
   the booking-window weights (default: equal weight, configurable per
   route) to get a single representative route fare for the period.

3. Compute a *price relative* for each route: current representative
   fare / base-period representative fare, i.e. P_t / P_0.

4. The index is the weighted arithmetic mean of price relatives, using
   each route's configured basket weight (sum of weights = 1.0),
   multiplied by 100 (so the base period = 100.0):

        APIx_t = 100 * sum_r( w_r * (P_r,t / P_r,0) )

   This is a *modified Laspeyres* formula: weights are fixed at
   configuration time (not re-derived from spend shares each period),
   which keeps the index simple, transparent and reproducible — the
   standard approach for CPI sub-indices where continuous expenditure
   weighting data isn't available in real time.

5. Route contribution to index-level change is:

        contribution_r = w_r * (P_r,t / P_r,0 - 1) * 100

   which sums (approximately) to (APIx_t - 100).

6. Airline contribution is computed analogously by re-running steps 1-3
   restricted to each airline's observations, weighted by that airline's
   *observed share of valid observations* in the current period (a
   transparent, reproducible proxy for market-share weighting).

Reproducibility
-----------------
Given an identical (observations_df, IndexConfig, base_period, as_of_period)
this module is a pure function: no randomness, no wall-clock reads inside
the computation, deterministic pandas aggregation (median with numpy),
and stable sort orders. Same inputs -> byte-identical output every run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

METHODOLOGY_VERSION = "APIx-v1.0.0"


@dataclass
class IndexConfig:
    base_period: str  # e.g. "2026-01" (a month) or an explicit ISO date range label
    route_weights: dict  # {"DEL-BOM": 0.12, ...} must sum to ~1.0
    booking_window_weights: Optional[dict] = None  # {"T+1":..,"T+7":..,...} sums to 1.0; None = equal weight
    include_suspicious: bool = False  # whether SUSPICIOUS-flagged fares are included (down-weighted context)
    methodology_version: str = METHODOLOGY_VERSION

    def eligible_statuses(self) -> list:
        return ["VALID", "SUSPICIOUS"] if self.include_suspicious else ["VALID"]

    def validate(self) -> list:
        problems = []
        total_w = sum(self.route_weights.values())
        if not (0.98 <= total_w <= 1.02):
            problems.append(f"route_weights sum to {total_w:.4f}, expected ~1.0")
        if self.booking_window_weights:
            bw_total = sum(self.booking_window_weights.values())
            if not (0.98 <= bw_total <= 1.02):
                problems.append(f"booking_window_weights sum to {bw_total:.4f}, expected ~1.0")
        return problems


@dataclass
class IndexResult:
    index_value: float
    base_period: str
    as_of_period: str
    methodology_version: str
    change_from_base_pct: float
    route_contributions: dict = field(default_factory=dict)
    airline_contributions: dict = field(default_factory=dict)
    route_fares: dict = field(default_factory=dict)  # route -> {period_fare, base_fare, relative}
    calculation_breakdown: list = field(default_factory=list)
    n_observations_used: int = 0
    routes_missing_data: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "index_value": round(self.index_value, 2),
            "base_period": self.base_period,
            "as_of_period": self.as_of_period,
            "methodology_version": self.methodology_version,
            "change_from_base_pct": round(self.change_from_base_pct, 3),
            "route_contributions": {k: round(v, 4) for k, v in self.route_contributions.items()},
            "airline_contributions": {k: round(v, 4) for k, v in self.airline_contributions.items()},
            "route_fares": self.route_fares,
            "calculation_breakdown": self.calculation_breakdown,
            "n_observations_used": self.n_observations_used,
            "routes_missing_data": self.routes_missing_data,
        }


def _period_label(d) -> str:
    d = pd.to_datetime(d)
    return f"{d.year:04d}-{d.month:02d}"


def _route_representative_fare(df: pd.DataFrame, origin: str, dest: str, period_label: str,
                                config: IndexConfig) -> Optional[float]:
    """Median total_fare for a route within a period, aggregated across
    booking windows using configured (or equal) booking-window weights."""
    sub = df[
        (df["origin"] == origin) & (df["destination"] == dest) &
        (df["period_label"] == period_label) &
        (df["data_quality_status"].isin(config.eligible_statuses()))
    ]
    if sub.empty:
        return None

    windows = sorted(sub["booking_window_days"].dropna().unique())
    if not windows:
        return float(np.median(sub["total_fare"]))

    weights = config.booking_window_weights or {}
    per_window_fare = {}
    for w in windows:
        wsub = sub[sub["booking_window_days"] == w]
        if not wsub.empty:
            per_window_fare[w] = float(np.median(wsub["total_fare"]))

    if not per_window_fare:
        return None

    if weights:
        # match window value to nearest configured T+n bucket key, e.g. "T+7"
        def _bucket_key(w):
            return f"T+{int(w)}"
        used = {k: v for k, v in per_window_fare.items() if _bucket_key(k) in weights}
        if used:
            wsum = sum(weights[_bucket_key(k)] for k in used)
            return sum(v * weights[_bucket_key(k)] for k, v in used.items()) / wsum

    # default: equal weight across whatever windows were observed
    return float(np.mean(list(per_window_fare.values())))


def compute_index(observations_df: pd.DataFrame, config: IndexConfig, as_of_period: str) -> IndexResult:
    problems = config.validate()
    if problems:
        raise ValueError(f"Invalid IndexConfig: {'; '.join(problems)}")

    df = observations_df.copy()
    # Vectorized period labelling: `_period_label` applied per-row forces
    # pandas to regex-guess the date format for every single row (~19s on
    # ~7k rows). Converting once then using dt.strftime is byte-identical
    # and ~100x faster, preserving the reproducibility contract.
    df["period_label"] = pd.to_datetime(df["travel_date"]).dt.strftime("%Y-%m")

    breakdown = [
        f"Methodology {config.methodology_version}: modified Laspeyres route-weighted index.",
        f"Base period = {config.base_period}, as-of period = {as_of_period}.",
        f"Eligible data-quality statuses: {config.eligible_statuses()}.",
    ]

    route_relatives = {}
    route_fares_out = {}
    missing = []
    n_used = 0

    for route_key, w_r in config.route_weights.items():
        origin, dest = route_key.split("-")
        base_fare = _route_representative_fare(df, origin, dest, config.base_period, config)
        period_fare = _route_representative_fare(df, origin, dest, as_of_period, config)

        if base_fare is None or period_fare is None:
            missing.append(route_key)
            continue

        relative = period_fare / base_fare
        route_relatives[route_key] = relative
        route_fares_out[route_key] = {
            "base_period_fare": round(base_fare, 2),
            "as_of_period_fare": round(period_fare, 2),
            "relative": round(relative, 4),
            "weight": w_r,
        }
        n_used += len(df[
            (df["origin"] == origin) & (df["destination"] == dest) &
            (df["period_label"] == as_of_period) &
            (df["data_quality_status"].isin(config.eligible_statuses()))
        ])

    if not route_relatives:
        raise ValueError("No routes had sufficient data in both base and as-of periods; "
                          "index cannot be computed. Check data availability.")

    # Renormalize weights across routes that actually had data, so the
    # index is still meaningful even if some routes are temporarily
    # SOURCE UNAVAILABLE. This is disclosed explicitly in the breakdown.
    available_weight_sum = sum(config.route_weights[r] for r in route_relatives)
    breakdown.append(
        f"{len(route_relatives)}/{len(config.route_weights)} configured routes had data; "
        f"weights renormalized (available weight mass = {available_weight_sum:.4f})."
    )
    if missing:
        breakdown.append(f"Routes with no data (excluded, shown as SOURCE UNAVAILABLE): {missing}.")

    index_value = 0.0
    contributions = {}
    for route_key, relative in route_relatives.items():
        norm_w = config.route_weights[route_key] / available_weight_sum
        index_value += norm_w * relative
        contributions[route_key] = norm_w * (relative - 1) * 100

    index_value *= 100

    breakdown.append(f"APIx_t = 100 * sum(normalized_weight_r * price_relative_r) = {index_value:.4f}")

    # ---- Airline contribution (transparent proxy: within as-of period,
    # weight each airline by its share of valid observations) ----
    as_of_valid = df[
        (df["period_label"] == as_of_period) &
        (df["data_quality_status"].isin(config.eligible_statuses()))
    ]
    airline_contrib = {}
    if not as_of_valid.empty:
        shares = as_of_valid["airline"].value_counts(normalize=True)
        for airline, share in shares.items():
            a_base = df[
                (df["airline"] == airline) & (df["period_label"] == config.base_period) &
                (df["data_quality_status"].isin(config.eligible_statuses()))
            ]["total_fare"]
            a_now = as_of_valid[as_of_valid["airline"] == airline]["total_fare"]
            if len(a_base) == 0 or len(a_now) == 0:
                continue
            rel = float(np.median(a_now)) / float(np.median(a_base))
            airline_contrib[airline] = share * (rel - 1) * 100

    result = IndexResult(
        index_value=index_value,
        base_period=config.base_period,
        as_of_period=as_of_period,
        methodology_version=config.methodology_version,
        change_from_base_pct=index_value - 100.0,
        route_contributions=contributions,
        airline_contributions=airline_contrib,
        route_fares=route_fares_out,
        calculation_breakdown=breakdown,
        n_observations_used=n_used,
        routes_missing_data=missing,
    )
    return result


def compute_index_series(observations_df: pd.DataFrame, config: IndexConfig, periods: list) -> list:
    """Convenience wrapper: compute the index across a list of period
    labels (e.g. the last 6 months) for trend charts. Reproducible and
    deterministic — same inputs always yield the same series."""
    series = []
    for p in periods:
        try:
            r = compute_index(observations_df, config, p)
            series.append({"period": p, "index_value": round(r.index_value, 2),
                            "n_observations_used": r.n_observations_used})
        except ValueError:
            series.append({"period": p, "index_value": None, "n_observations_used": 0})
    return series
