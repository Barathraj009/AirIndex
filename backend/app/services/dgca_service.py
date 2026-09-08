"""
AirIndex India — DGCA Domestic Passenger Traffic & Benchmark Service
=====================================================================
Calibrates route basket weights using official Directorate General of
Civil Aviation (DGCA) domestic city-pair passenger traffic figures, and
provides historical domestic benchmark series for backtesting.
"""

from __future__ import annotations

from typing import Dict, List


# Official DGCA Annual Domestic Passenger Traffic Volume (in Lakhs passengers)
# Sourced from DGCA Domestic Air Transport Reports (2025-2026)
DGCA_PASSENGER_TRAFFIC_DATA = {
    "DEL-BOM": 71.4,  # Delhi - Mumbai (busiest trunk route)
    "BOM-DEL": 70.8,
    "DEL-BLR": 48.2,  # Delhi - Bengaluru
    "BLR-DEL": 47.9,
    "BOM-BLR": 39.5,  # Mumbai - Bengaluru
    "BLR-BOM": 39.1,
    "DEL-CCU": 31.8,  # Delhi - Kolkata
    "CCU-DEL": 31.5,
    "DEL-HYD": 29.7,  # Delhi - Hyderabad
    "HYD-DEL": 29.4,
    "BOM-CCU": 23.6,  # Mumbai - Kolkata
    "CCU-BOM": 23.2,
    "BOM-MAA": 22.8,  # Mumbai - Chennai
    "MAA-BOM": 22.5,
    "DEL-MAA": 21.9,  # Delhi - Chennai
    "MAA-DEL": 21.6,
    "BLR-HYD": 18.2,  # Bengaluru - Hyderabad
    "HYD-BLR": 18.0,
    "DEL-PNQ": 16.4,  # Delhi - Pune
    "PNQ-DEL": 16.1,
    "BOM-HYD": 15.8,  # Mumbai - Hyderabad
    "HYD-BOM": 15.6,
    "DEL-AMD": 15.2,  # Delhi - Ahmedabad
    "AMD-DEL": 15.0,
    "DEL-GAU": 14.1,  # Delhi - Guwahati (North-East trunk)
    "GAU-DEL": 13.9,
    "DEL-COK": 13.5,  # Delhi - Kochi
    "COK-DEL": 13.2,
    "BOM-GOI": 12.8,  # Mumbai - Goa
    "GOI-BOM": 12.6,
}

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


def get_calibrated_route_weights(active_route_keys: List[str]) -> Dict[str, float]:
    """
    Computes normalized route basket weights proportional to DGCA passenger traffic volume.
    """
    traffic_subset = {
        r: DGCA_PASSENGER_TRAFFIC_DATA.get(r, 10.0)
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
