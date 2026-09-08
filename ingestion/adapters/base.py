"""
AirIndex India — Source Adapter Interface
============================================
Every data source (a specific airline's website, an OTA, a public dataset,
or the demo generator) implements this interface. The ingestion
orchestrator (backend/app/api/ingestion.py, Phase 2) only ever talks to
this interface — it never knows the details of any specific source. This
is what requirement #2 in the spec calls "a reusable source-adapter
architecture so different airlines/sources can be added without changing
the core system."

Contract
---------
- `collect(routes, booking_windows, as_of)` returns a pandas DataFrame
  in *raw* form (source-specific column names are fine) OR raises
  `SourceUnavailableError`.
- Adapters must NEVER fabricate data. If a source cannot be reached,
  raise SourceUnavailableError — the orchestrator will record a
  SOURCE UNAVAILABLE status for that run and move on. It must never
  crash the overall ingestion pipeline (spec section 12).
- `to_common_format(raw_df)` maps the adapter's raw columns onto the
  canonical field names consumed by
  backend/app/services/data_processing.normalize_raw_observations
  (origin, destination, airline, travel_date, collection_timestamp,
  booking_window_days, base_fare, taxes_fees, total_fare, ...).
- `source_name` / `source_type` identify the adapter for provenance
  and for the LIVE / PUBLIC / DEMO labeling shown in the UI.
- Adapters must respect robots.txt and each site's terms of service,
  apply reasonable rate limiting, and must NEVER attempt to bypass
  CAPTCHA, login walls, or anti-bot protections. See
  ingestion/adapters/airline_adapter_template.py for the documented
  pattern real airline adapters should follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd


class SourceUnavailableError(Exception):
    """Raised by an adapter when a source cannot currently be reached
    (robots.txt disallow, network failure, structural site change,
    CAPTCHA/anti-bot wall encountered, rate limit exhausted, etc.).
    The orchestrator catches this per-adapter so one failing source
    never takes down the rest of the ingestion run."""

    def __init__(self, source_name: str, reason: str):
        self.source_name = source_name
        self.reason = reason
        super().__init__(f"SOURCE UNAVAILABLE: {source_name} ({reason})")


@dataclass
class CollectionRequest:
    routes: list           # e.g. ["DEL-BOM", "DEL-BLR"]
    booking_windows: list  # e.g. [1, 7, 15, 30, 45]
    as_of: date             # the "today" the collection run represents


class BaseSourceAdapter(ABC):
    source_name: str = "UNSET"
    source_type: str = "UNSET"  # LIVE_SCRAPE / PUBLIC_DATASET / DEMO_SIMULATED

    @abstractmethod
    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        """Collect raw fare observations. Must raise SourceUnavailableError
        rather than returning partial/fabricated data on failure."""
        raise NotImplementedError

    @abstractmethod
    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Map adapter-specific columns onto the canonical schema fields
        consumed by data_processing.normalize_raw_observations. Does not
        need to fill every canonical column — normalize_raw_observations
        fills gaps and computes derived fields."""
        raise NotImplementedError

    def run(self, request: CollectionRequest) -> tuple[Optional[pd.DataFrame], Optional[str]]:
        """Convenience wrapper used by the orchestrator: returns
        (dataframe, None) on success or (None, reason) on failure —
        never raises, so a bad source can't crash a scheduled run."""
        try:
            raw = self.collect(request)
            return self.to_common_format(raw), None
        except SourceUnavailableError as e:
            return None, e.reason
        except Exception as e:  # noqa: BLE001 - deliberately broad: any adapter
            # bug must degrade to SOURCE UNAVAILABLE, never crash the run.
            return None, f"unexpected_adapter_error: {e}"
