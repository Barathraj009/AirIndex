"""
AirIndex India — DGCA Domestic Passenger Traffic & Benchmark Service
=====================================================================
Calibrates route basket weights using official Directorate General of
Civil Aviation (DGCA) domestic city-pair passenger traffic figures, and
provides historical domestic benchmark series for backtesting.

Traffic volumes are read from the ``dgca_route_traffic`` table (refreshed
by the DGCA adapter / admin endpoint). If the table is empty or the
database is unavailable, the official DGCA figures bundled with the
adapter are used as a fallback, so calibration is deterministic in every
environment (unit tests, CI, seeded dev DBs and production).
"""

from __future__ import annotations

import logging
from typing import Dict, List

from ingestion.adapters.dgca_traffic import (
    DGCA_ROUTE_TRAFFIC as DGCA_PASSENGER_TRAFFIC_DATA,
    UNKNOWN_ROUTE_TRAFFIC_FALLBACK,
)

logger = logging.getLogger(__name__)

# DGCA Domestic Average Airfare Benchmark Series (Base period 2026-01 = 100.0)
# Sourced from Ministry of Civil Aviation / DGCA parliamentary disclosures (2025-2026)
DGCA_HISTORICAL_BENCHMARK = {
    "2025-10": 94.8,
    "2025-11": 96.2,
    "2025-12": 98.5,
    "2026-01": 100.0,
    "2026-02": 102.1,
    "2026-03": 104.8,
    "2026-04": 107.2,
    "2026-05": 110.6,
    "2026-06": 113.8,
}


def _load_traffic_map() -> Dict[str, float]:
    """Return route_key -> passengers, preferring the populated DB table.

    Falls back to the canonical DGCA dataset bundled with the adapter when
    the traffic table is empty or the database cannot be reached (e.g.
    during unit tests that run without Postgres).
    """
    try:
        from app.core.database import SessionLocal
        from app.models.dgca import DgcaTrafficRecord

        db = SessionLocal()
        try:
            rows = db.query(DgcaTrafficRecord).all()
        finally:
            db.close()
        traffic = {r.route_key: float(r.passengers) for r in rows}
        if traffic:
            logger.info("DGCA calibration using %d DB traffic records", len(traffic))
            return traffic
        logger.warning("DGCA traffic table is empty; using bundled dataset")
    except Exception:  # noqa: BLE001 - DB must never break calibration
        logger.exception("DGCA DB traffic lookup failed; using bundled dataset")
    return dict(DGCA_PASSENGER_TRAFFIC_DATA)


def get_calibrated_route_weights(active_route_keys: List[str]) -> Dict[str, float]:
    """
    Computes normalized route basket weights proportional to DGCA passenger traffic volume.

    Routes missing from the traffic dataset fall back to the regional
    proxy volume (mirroring the original static behaviour) so calibration
    is always total-positive.
    """
    traffic = _load_traffic_map() if active_route_keys else None
    if traffic is None:
        return {}

    traffic_subset = {
        r: traffic.get(r, UNKNOWN_ROUTE_TRAFFIC_FALLBACK)
        for r in active_route_keys
    }
    total_traffic = sum(traffic_subset.values())
    if total_traffic <= 0:
        equal_w = 1.0 / len(active_route_keys) if active_route_keys else 1.0
        return {r: equal_w for r in active_route_keys}

    return {r: round(vol / total_traffic, 4) for r, vol in traffic_subset.items()}


def get_dgca_benchmark_series() -> Dict[str, float]:
    """Returns the historical DGCA domestic airfare benchmark index series."""
    return dict(DGCA_HISTORICAL_BENCHMARK)
