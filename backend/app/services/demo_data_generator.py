"""
AirIndex India — Demo / Synthetic Data Generator
===================================================
Generates a realistic-but-CLEARLY-LABELLED synthetic airfare dataset so the
full platform (dashboard, index engine, data-quality monitor, backtesting)
can be demonstrated end-to-end even when no live source is reachable.

Every row is tagged:
    source        = "DEMO_SIMULATED"
    source_type   = "DEMO_SIMULATED"

This is never to be presented as LIVE or PUBLIC data by any downstream
consumer (see backend/app/services/data_processing.py SourceType enum).

Design notes on realism
-------------------------
- Base fares differ by route "distance tier" (metro-metro trunk routes are
  cheaper per-km than thin regional routes).
- Fares rise as the booking window shrinks (T+1 costs more than T+45),
  modeled with a convex booking-curve multiplier.
- Each airline has a persistent relative positioning (e.g. a low-cost
  carrier trending below a full-service carrier) plus day-to-day noise.
- A slow-moving "market drift" term is applied per month so the resulting
  index has a plausible trend rather than pure noise.
- A small percentage of rows are deliberately injected as
  cancelled/sold-out, missing fields, or extreme outliers, so the data
  processing pipeline has something real to catch and demonstrate.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, date

import numpy as np
import pandas as pd

RANDOM_SEED = 42

AIRLINES = {
    # name: (relative_position multiplier, is_lcc, real_market_share)
    #
    # market_share is REAL, cited data: DGCA-reported domestic market
    # share for August 2026 (per Deccan Herald's reporting of DGCA's
    # monthly traffic data, retrieved via web search during this build —
    # see docs/ROBOTS_TXT_FINDINGS.md's sibling research). IndiGo 64.2%,
    # Air India Group (Air India + Air India Express combined) 27.3%,
    # Akasa Air 5.4%, SpiceJet 2%. The Air India Group figure is split
    # here 20.3%/7.0% between Air India and Air India Express as an
    # ESTIMATE (DGCA reports the group combined, not the two brands
    # separately in the source found) — that split is illustrative, the
    # group total is not. Used to weight how often each airline appears
    # in the generated observations, so the demo's implied airline mix
    # is grounded in real reported shares rather than an even 5-way split.
    "IndiGo": (0.97, True, 0.642),
    "Air India": (1.10, False, 0.203),
    "Air India Express": (0.90, True, 0.070),
    "Akasa Air": (0.98, True, 0.054),
    "SpiceJet": (0.95, True, 0.020),
}

# Representative Indian domestic route basket.
# Weights are ILLUSTRATIVE (loosely proportional to approximate trunk-route
# traffic share) — NOT official MoSPI/DGCA weights. An administrator can
# override these via the admin configuration (see routes table / API).
ROUTE_BASKET = {
    # route: (weight, base_fare_inr, distance_tier)
    "DEL-BOM": (0.14, 5200, "trunk"),
    "DEL-BLR": (0.11, 5600, "trunk"),
    "BOM-BLR": (0.09, 4200, "trunk"),
    "DEL-MAA": (0.08, 6200, "trunk"),
    "DEL-CCU": (0.07, 5800, "trunk"),
    "BOM-MAA": (0.06, 5400, "trunk"),
    "BLR-HYD": (0.06, 3400, "regional"),
    "DEL-HYD": (0.07, 5600, "trunk"),
    "BOM-CCU": (0.05, 6200, "trunk"),
    "DEL-PNQ": (0.05, 5400, "regional"),
    "DEL-GOI": (0.05, 5800, "regional"),
    "BLR-MAA": (0.04, 3200, "regional"),
    "DEL-COK": (0.04, 6800, "regional"),
    "BOM-GOI": (0.03, 3600, "regional"),
    "CCU-BLR": (0.03, 6600, "regional"),
    "DEL-ATQ": (0.03, 4600, "regional"),
}

BOOKING_WINDOWS = [1, 7, 15, 30, 45]

# Convex booking curve: multiplier applied as (days-to-travel) shrinks.
def _booking_multiplier(days_out: int) -> float:
    if days_out >= 45:
        return 0.90
    if days_out >= 30:
        return 1.00
    if days_out >= 15:
        return 1.12
    if days_out >= 7:
        return 1.35
    return 1.75  # T+1


def _month_drift(month_index: int) -> float:
    """Slow upward drift + a seasonal (festival-season) bump, deterministic
    given month_index (0 = first month of the generated window)."""
    trend = 1.0 + 0.006 * month_index  # ~0.6%/month gentle inflation drift
    seasonal = 1.0
    # crude festival bump for Oct/Nov (index months 9,10 if starting Jan)
    return trend, seasonal


def generate_demo_observations(
    start_date: date,
    n_months: int = 6,
    collections_per_week: int = 2,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """Generates synthetic fare observations across ROUTE_BASKET x AIRLINES
    x BOOKING_WINDOWS x a schedule of collection dates spanning n_months.

    Returns a dataframe already in the columns expected by
    data_processing.normalize_raw_observations (i.e. it can be fed directly
    into run_pipeline(df, source="DEMO_SIMULATED", source_type="DEMO_SIMULATED")).
    """
    rng = np.random.default_rng(seed)
    random.seed(seed)

    rows = []
    total_days = n_months * 30
    collection_dates = [
        start_date + timedelta(days=i)
        for i in range(0, total_days, max(1, 7 // collections_per_week))
    ]

    for collection_date in collection_dates:
        month_index = (collection_date.year - start_date.year) * 12 + (collection_date.month - start_date.month)
        trend, seasonal = _month_drift(month_index)

        for route, (weight, base_fare, tier) in ROUTE_BASKET.items():
            origin, dest = route.split("-")

            for window in BOOKING_WINDOWS:
                travel_date = collection_date + timedelta(days=window)

                max_share = max(s for _, _, s in AIRLINES.values())
                for airline, (pos_mult, is_lcc, market_share) in AIRLINES.items():
                    # Sample each airline's presence in proportion to its
                    # REAL reported market share (see the AIRLINES comment
                    # above for the cited source) rather than an arbitrary
                    # thinning rule — IndiGo (64.2% share) appears in
                    # nearly every slot, SpiceJet (2% share) rarely does,
                    # which is what the real domestic market actually
                    # looks like.
                    inclusion_probability = market_share / max_share
                    if rng.random() > inclusion_probability:
                        continue

                    noise = rng.normal(1.0, 0.045)
                    weekday_bump = 1.08 if travel_date.weekday() in (4, 6) else 1.0  # Fri/Sun pricier

                    fare = (
                        base_fare
                        * pos_mult
                        * _booking_multiplier(window)
                        * trend
                        * seasonal
                        * weekday_bump
                        * noise
                    )

                    base_component = round(fare * 0.72, 2)
                    taxes_component = round(fare * 0.28, 2)
                    total = round(base_component + taxes_component, 2)

                    availability = "AVAILABLE"
                    r = rng.random()
                    if r < 0.015:
                        availability = "SOLD_OUT"
                    elif r < 0.02:
                        availability = "CANCELLED"

                    # Inject a small number of deliberate data-quality problems
                    # so the pipeline (and Data Quality dashboard page) has
                    # real things to catch in the demo.
                    inject = rng.random()
                    if inject < 0.006:
                        total = total * 6.5  # extreme outlier
                    elif inject < 0.010:
                        total = round(total * 0.15, 2)  # implausibly low (bad scrape)
                    elif inject < 0.013:
                        total = np.nan  # missing fare

                    rows.append({
                        "origin": origin,
                        "destination": dest,
                        "airline": airline,
                        "flight_number": f"{airline[:2].upper()}{rng.integers(100, 999)}",
                        "travel_date": travel_date.isoformat(),
                        "collection_timestamp": datetime.combine(
                            collection_date, datetime.min.time()
                        ).isoformat(),
                        "booking_window_days": window,
                        "fare_class": random.choice(["ECONOMY_SAVER", "ECONOMY_FLEX"]),
                        "base_fare": base_component if pd.notna(total) else np.nan,
                        "taxes_fees": taxes_component if pd.notna(total) else np.nan,
                        "total_fare": total,
                        "currency": "INR",
                        "availability_status": availability,
                        "source": "DEMO_SIMULATED",
                        "source_type": "DEMO_SIMULATED",
                        "data_quality_status": np.nan,   # filled in by the processing pipeline
                        "quality_flags": np.nan,
                    })

    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    import sys
    from pathlib import Path

    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/demo_generated.csv")
    df = generate_demo_observations(start_date=date(2026, 1, 1), n_months=8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} synthetic DEMO_SIMULATED observations -> {out_path}")
