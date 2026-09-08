"""
AirIndex India — MoSPI CPI Augmentation Engine
===============================================
Models the integration of the real-time Airfare Price Index (APIx)
into India's official Consumer Price Index (Base 2012=100) published
by the Ministry of Statistics and Programme Implementation (MoSPI).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np


HISTORICAL_MOSPI_CPI = {
    "2025-10": {"general_cpi": 191.2, "transport_cpi": 164.8, "airfare_subindex_lagged": 142.1},
    "2025-11": {"general_cpi": 192.4, "transport_cpi": 165.2, "airfare_subindex_lagged": 143.0},
    "2025-12": {"general_cpi": 193.1, "transport_cpi": 166.0, "airfare_subindex_lagged": 145.2},
    "2026-01": {"general_cpi": 193.8, "transport_cpi": 166.5, "airfare_subindex_lagged": 145.8},
    "2026-02": {"general_cpi": 194.2, "transport_cpi": 167.1, "airfare_subindex_lagged": 146.3},
    "2026-03": {"general_cpi": 194.9, "transport_cpi": 167.8, "airfare_subindex_lagged": 146.9},
    "2026-04": {"general_cpi": 195.6, "transport_cpi": 168.4, "airfare_subindex_lagged": 147.5},
    "2026-05": {"general_cpi": 196.3, "transport_cpi": 169.1, "airfare_subindex_lagged": 148.0},
    "2026-06": {"general_cpi": 197.1, "transport_cpi": 169.9, "airfare_subindex_lagged": 148.6},
}

DEFAULT_TRANSPORT_WEIGHT = 0.0859   # 8.59%
DEFAULT_AIRFARE_IN_CPI_WEIGHT = 0.0020  # 0.20% of General CPI


@dataclass
class CpiSimulationResult:
    airfare_weight_pct: float
    transport_weight_pct: float
    points: List[Dict]
    mean_headline_delta_bps: float
    max_headline_delta_bps: float
    lag_reduction_days_est: int
    policy_summary: str

    def as_dict(self) -> dict:
        return {
            "airfare_weight_pct": self.airfare_weight_pct,
            "transport_weight_pct": self.transport_weight_pct,
            "points": self.points,
            "mean_headline_delta_bps": round(self.mean_headline_delta_bps, 2),
            "max_headline_delta_bps": round(self.max_headline_delta_bps, 2),
            "lag_reduction_days_est": self.lag_reduction_days_est,
            "policy_summary": self.policy_summary,
        }


def simulate_cpi_augmentation(
    apix_series: Dict[str, float],
    airfare_weight_in_cpi: float = DEFAULT_AIRFARE_IN_CPI_WEIGHT,
    transport_group_weight: float = DEFAULT_TRANSPORT_WEIGHT,
    base_period: str = "2026-01",
) -> CpiSimulationResult:
    points = []
    deltas = []

    weight_air_in_transport = airfare_weight_in_cpi / transport_group_weight if transport_group_weight > 0 else 0.0233
    weight_other_in_transport = 1.0 - weight_air_in_transport

    sorted_periods = sorted(p for p in apix_series if p in HISTORICAL_MOSPI_CPI)
    if not sorted_periods:
        sorted_periods = sorted(HISTORICAL_MOSPI_CPI.keys())

    for period in sorted_periods:
        hist = HISTORICAL_MOSPI_CPI.get(period)
        if not hist:
            continue

        off_gen = hist["general_cpi"]
        off_trans = hist["transport_cpi"]
        lagged_air = hist["airfare_subindex_lagged"]

        apix_val = apix_series.get(period, 100.0)
        apix_scaled = (apix_val / 100.0) * lagged_air

        other_transport_cpi = (off_trans - (weight_air_in_transport * lagged_air)) / weight_other_in_transport
        aug_transport = (weight_other_in_transport * other_transport_cpi) + (weight_air_in_transport * apix_scaled)

        transport_diff = aug_transport - off_trans
        aug_general = off_gen + (transport_group_weight * transport_diff)

        delta_bps = (aug_general - off_gen) * 100.0
        deltas.append(delta_bps)

        points.append({
            "period": period,
            "official_general_cpi": round(off_gen, 2),
            "augmented_general_cpi": round(aug_general, 2),
            "official_transport_cpi": round(off_trans, 2),
            "augmented_transport_cpi": round(aug_transport, 2),
            "apix_value": round(apix_val, 2),
            "inflation_delta_bps": round(delta_bps, 2),
        })

    mean_delta = float(np.mean(deltas)) if deltas else 0.0
    max_delta = float(np.max(np.abs(deltas))) if deltas else 0.0

    summary = (
        f"Integrating real-time APIx at {airfare_weight_in_cpi*100:.2f}% CPI weight adjusted headline CPI "
        f"by an average of {mean_delta:+.1f} bps (peak {max_delta:.1f} bps). "
        f"Captures dynamic surge airfare variations with ~45 days reduced reporting lag vs static quarterly surveys."
    )

    return CpiSimulationResult(
        airfare_weight_pct=round(airfare_weight_in_cpi * 100, 3),
        transport_weight_pct=round(transport_group_weight * 100, 2),
        points=points,
        mean_headline_delta_bps=mean_delta,
        max_headline_delta_bps=max_delta,
        lag_reduction_days_est=45,
        policy_summary=summary,
    )
