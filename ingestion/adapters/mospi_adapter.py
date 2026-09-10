"""
AirIndex India — MoSPI CPI Transport Data Adapter (Live)
========================================================
Fetches REAL Consumer Price Index (CPI) transport data from India's
Ministry of Statistics and Programme Implementation via their public API.

Primary target: Code 07.3.3.1 = "Passenger transport by air, domestic"
  - This is the official CPI sub-component for domestic airfares
  - Base year 2024=100, released monthly on the 12th
  - Source: https://esankhyiki.mospi.gov.in
  - API: https://api.mospi.gov.in/api/cpi/getCPIData

Also fetches related transport CPI components for context:
  - 07 = Transport division overall
  - 07.3 = Passenger transport services
  - 07.2.2 = Fuels and lubricants (fuel cost driver)
  - 07.3.1 = Rail transport (comparison benchmark)
  - 07.3.2 = Road transport (comparison benchmark)
"""

from __future__ import annotations

import logging
import ssl
from datetime import date, datetime
from typing import Optional

import httpx
import pandas as pd

from ingestion.adapters.base import BaseSourceAdapter, CollectionRequest, SourceUnavailableError

logger = logging.getLogger(__name__)

MOSPI_API_BASE = "https://api.mospi.gov.in/api/cpi/getCPIData"


def _mospi_ssl_context() -> ssl.SSLContext:
    """SSL context tolerant of MoSPI's legacy TLS renegotiation."""
    ctx = ssl.create_default_context()
    try:
        ctx.options |= 0x4  # SSL_OP_LEGACY_SERVER_CONNECT
    except (ValueError, OSError):
        pass
    return ctx

# CPI codes we care about — these map to real MoSPI published data
AIRFARE_CODE = "07.3.3.1"          # Passenger transport by air, domestic
TRANSPORT_DIVISION_CODE = "07"     # Transport division overall
PASSENGER_TRANSPORT_CODE = "07.3"  # Passenger transport services
FUEL_CODE = "07.2.2"               # Fuels and lubricants for personal transport
RAIL_CODE = "07.3.1"               # Passenger transport by railway
ROAD_CODE = "07.3.2"               # Passenger transport by road

# Map CPI codes to our route/airline model
# We distribute airfare CPI across representative domestic routes
REPRESENTATIVE_ROUTES = [
    ("DEL", "BOM"), ("DEL", "BLR"), ("BOM", "BLR"), ("DEL", "CCU"),
    ("DEL", "HYD"), ("BLR", "HYD"), ("DEL", "MAA"), ("BOM", "MAA"),
]

ROUTE_WEIGHTS = {
    "DEL-BOM": 0.13, "DEL-BLR": 0.11, "BOM-BLR": 0.09, "DEL-CCU": 0.08,
    "DEL-HYD": 0.09, "BLR-HYD": 0.07, "DEL-MAA": 0.08, "BOM-MAA": 0.07,
    "DEL-GOI": 0.05, "BOM-GOI": 0.04, "BLR-CCU": 0.04, "DEL-TRV": 0.04,
    "BOM-HYD": 0.03, "DEL-PNQ": 0.02, "BLR-MAA": 0.02, "BOM-CCU": 0.02,
}

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


class MospiCpiAdapter(BaseSourceAdapter):
    """Fetches REAL CPI airfare data from MoSPI's public API."""

    source_name = "MOSPI_CPI"
    source_type = "PUBLIC_DATASET"

    def __init__(self):
        self._base_fare_index = 5500.0  # Approx average domestic fare INR at base period (2024)

    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        """Fetch CPI transport data from MoSPI public API."""
        try:
            all_records = []
            # Fetch multiple years of data for time series
            years = ["2025", "2026"]

with httpx.Client(timeout=30.0, follow_redirects=True, verify=_mospi_ssl_context()) as client:
                for year_str in years:
                    for page in range(1, 25):
                        try:
                            resp = client.get(MOSPI_API_BASE, params={
                                "base_year": 2024,
                                "division_code": 7,
                                "state_code": 1,
                                "sector_code": 3,
                                "year": year_str,
                                "limit": 50,
                                "page": page,
                            })
                            resp.raise_for_status()
                            body = resp.json()

                            if not body.get("statusCode") or not body.get("data"):
                                break

                            records = body["data"]
                            meta = body.get("meta_data", {})

                            for rec in records:
                                code = rec.get("code", "")
                                # Only keep relevant CPI codes
                                if code in (AIRFARE_CODE, TRANSPORT_DIVISION_CODE,
                                            PASSENGER_TRANSPORT_CODE, FUEL_CODE,
                                            RAIL_CODE, ROAD_CODE):
                                    all_records.append(rec)

                            total_pages = meta.get("totalPages", 1)
                            if page >= total_pages:
                                break

                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 400:
                                break
                            raise

            if not all_records:
                raise SourceUnavailableError(
                    self.source_name,
                    "No CPI transport data returned from MoSPI API"
                )

            df = pd.DataFrame(all_records)
            logger.info(f"MoSPI API: fetched {len(df)} CPI transport records")
            return df

        except SourceUnavailableError:
            raise
        except httpx.ConnectError as e:
            raise SourceUnavailableError(self.source_name, f"Cannot reach MoSPI API: {e}")
        except httpx.TimeoutException:
            raise SourceUnavailableError(self.source_name, "MoSPI API request timed out")
        except Exception as e:
            raise SourceUnavailableError(self.source_name, f"Error fetching MoSPI data: {e}")

    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Map MoSPI CPI records to canonical fare observation schema."""
        rows = []
        now = datetime.utcnow()

        for _, rec in raw_df.iterrows():
            code = rec.get("code", "")
            index_val = float(rec.get("index", 100))
            inflation_pct = float(rec.get("inflation", 0) or 0)
            year = str(rec.get("year", ""))
            month_name = str(rec.get("month", ""))

            # Parse date
            month_num = MONTH_MAP.get(month_name.lower(), 0)
            if not month_num or not year.isdigit():
                continue
            travel_date = date(int(year), month_num, 15)

            # The CPI index value (base 2024=100) represents price level
            # Convert to approximate INR fare using base fare assumption
            # At base period (2024), index=100 means fare = base_fare
            estimated_fare = self._base_fare_index * (index_val / 100.0)

            # Distribute across routes weighted by traffic share
            for route_key, route_weight in ROUTE_WEIGHTS.items():
                origin, destination = route_key.split("-")

                # Route-specific fare adjustment (longer routes cost more)
                route_multiplier = self._route_distance_multiplier(origin, destination)
                route_fare = estimated_fare * route_multiplier

                rows.append({
                    "origin": origin,
                    "destination": destination,
                    "airline": "CPI_AIRFARE_BENCHMARK",
                    "flight_number": f"MOSPI_{code}",
                    "travel_date": travel_date.isoformat(),
                    "collection_timestamp": now.isoformat(),
                    "booking_window_days": 30,
                    "fare_class": "CPI_BENCHMARK",
                    "base_fare": round(route_fare * 0.72, 2),
                    "taxes_fees": round(route_fare * 0.28, 2),
                    "total_fare": round(route_fare, 2),
                    "currency": "INR",
                    "availability_status": "AVAILABLE",
                    "source": self.source_name,
                    "source_type": self.source_type,
                    "data_quality_status": "VALID",
                    "quality_flags": (
                        f"cpi_code={code};cpi_index={index_val};"
                        f"inflation_yoy={inflation_pct};"
                        f"source=esankhyiki.mospi.gov.in"
                    ),
                })

        if not rows:
            raise SourceUnavailableError(self.source_name, "No valid CPI records to map")

        return pd.DataFrame(rows)

    def _route_distance_multiplier(self, origin: str, destination: str) -> float:
        """Approximate fare multiplier based on route distance tier."""
        short_haul = {"DEL-HYD", "BLR-HYD", "BOM-HYD", "DEL-PNQ", "BLR-MAA", "DEL-CCU"}
        medium_haul = {"DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-MAA", "BOM-MAA", "BOM-GOI", "DEL-GOI"}
        long_haul = {"DEL-TRV", "BLR-CCU", "BOM-CCU"}

        route = f"{origin}-{destination}"
        if route in short_haul:
            return 0.65
        elif route in long_haul:
            return 1.35
        elif route in medium_haul:
            return 1.0
        return 1.0


def fetch_mospi_cpi_series() -> dict:
    """Fetch the full CPI airfare time series from MoSPI for use by cpi_engine.
    Returns dict of {period_label: {index, inflation_yoy, code, description}}."""
    series = {}
    years = ["2024", "2025", "2026"]

    with httpx.Client(timeout=30.0, follow_redirects=True, verify=_mospi_ssl_context()) as client:
        for year_str in years:
            for page in range(1, 25):
                try:
                    resp = client.get(MOSPI_API_BASE, params={
                        "base_year": 2024,
                        "division_code": 7,
                        "state_code": 1,
                        "sector_code": 3,
                        "year": year_str,
                        "limit": 50,
                        "page": page,
                    })
                    resp.raise_for_status()
                    body = resp.json()

                    if not body.get("statusCode") or not body.get("data"):
                        break

                    for rec in body["data"]:
                        if rec.get("code") == AIRFARE_CODE:
                            month_name = str(rec.get("month", "")).lower()
                            month_num = MONTH_MAP.get(month_name, 0)
                            if month_num and year_str.isdigit():
                                period = f"{year_str}-{month_num:02d}"
                                series[period] = {
                                    "airfare_index": float(rec.get("index", 100)),
                                    "inflation_yoy": float(rec.get("inflation", 0) or 0),
                                    "code": AIRFARE_CODE,
                                    "description": "Passenger transport by air, domestic",
                                }

                    meta = body.get("meta_data", {})
                    if page >= meta.get("totalPages", 1):
                        break

                except Exception:
                    break

    return series
