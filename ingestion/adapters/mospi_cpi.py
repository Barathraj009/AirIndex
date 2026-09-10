"""
MoSPI CPI Airfare Index — Primary Data Source Adapter
======================================================
Fetches REAL Consumer Price Index airfare data from India's
Ministry of Statistics and Programme Implementation.

Target: Code 07.3.3.1 = "Passenger transport by air, domestic"
  - Official CPI sub-component for domestic airfares
  - Base year 2024=100
  - Published monthly around the 12th

Source: https://esankhyiki.mospi.gov.in
API: https://api.mospi.gov.in/api/cpi/getCPIData
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional, List, Dict

import httpx

logger = logging.getLogger(__name__)

MOSPI_API = "https://api.mospi.gov.in/api/cpi/getCPIData"

# CPI codes
AIRFARE_CODE = "07.3.3.1"          # Passenger transport by air, domestic
TRANSPORT_CODE = "07"               # Transport division
GENERAL_CODE = "00"                 # All items (General CPI)

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


class MospiCpiAirfareFetcher:
    """Fetches real CPI airfare data from MoSPI public API."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._base_url = MOSPI_API

    def fetch_all(self, years: Optional[List[str]] = None) -> Dict[str, Dict]:
        """Fetch CPI data for specified years.

        Returns dict keyed by period (YYYY-MM) with values:
          {airfare_index, transport_index, general_index, inflation_yoy}
        """
        if years is None:
            current_year = datetime.now().year
            years = [str(current_year - 1), str(current_year)]

        airfare = {}
        transport = {}
        general = {}

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for year_str in years:
                # Fetch Transport division (code 07) — contains airfare
                self._fetch_division(client, year_str, 7, airfare, transport)
                # Fetch General CPI (code 00)
                self._fetch_division(client, year_str, 0, general, {})

        # Build combined series
        all_periods = sorted(set(airfare.keys()) | set(transport.keys()) | set(general.keys()))
        series = {}

        for p in all_periods:
            air_idx = airfare.get(p, 100.0)
            trans_idx = transport.get(p, 100.0)
            gen_idx = general.get(p, 100.0)

            # Calculate YoY inflation for airfare
            year, month = p.split("-")
            prev_period = f"{int(year)-1}-{month}"
            prev_air = airfare.get(prev_period)
            inflation_yoy = None
            if prev_air and prev_air > 0:
                inflation_yoy = round(((air_idx - prev_air) / prev_air) * 100, 2)

            series[p] = {
                "airfare_index": air_idx,
                "transport_index": trans_idx,
                "general_index": gen_idx,
                "inflation_yoy": inflation_yoy,
            }

        logger.info(f"MoSPI: fetched {len(series)} months of CPI airfare data")
        return series

    def _fetch_division(
        self,
        client: httpx.Client,
        year_str: str,
        division_code: int,
        target_dict: Dict[str, float],
        secondary_dict: Optional[Dict[str, float]],
    ):
        """Fetch data for a specific division across all pages."""
        for page in range(1, 50):
            try:
                resp = client.get(self._base_url, params={
                    "base_year": 2024,
                    "division_code": division_code,
                    "state_code": 1,  # All India
                    "sector_code": 3,  # Combined (Rural + Urban)
                    "year": year_str,
                    "limit": 50,
                    "page": page,
                })
                resp.raise_for_status()
                body = resp.json()

                if not body.get("statusCode") or not body.get("data"):
                    break

                for rec in body["data"]:
                    code = rec.get("code", "")
                    period = self._parse_period(rec)
                    if not period:
                        continue

                    idx = float(rec.get("index", 100))

                    if code == AIRFARE_CODE:
                        target_dict[period] = idx
                    elif code == TRANSPORT_CODE and secondary_dict is not None:
                        secondary_dict[period] = idx
                    elif code == GENERAL_CODE:
                        target_dict[period] = idx

                meta = body.get("meta_data", {})
                if page >= meta.get("totalPages", 1):
                    break

            except Exception as e:
                logger.warning(f"MoSPI fetch error (page {page}): {e}")
                break

    def _parse_period(self, rec: dict) -> Optional[str]:
        """Parse month/year from MoSPI record into YYYY-MM format."""
        month_name = str(rec.get("month", "")).lower()
        month_num = MONTH_MAP.get(month_name, 0)
        year = str(rec.get("year", ""))
        if month_num and year.isdigit():
            return f"{year}-{month_num:02d}"
        return None


def fetch_mospi_airfare_index() -> List[Dict]:
    """Fetch MoSPI airfare CPI data and return as list of dicts for DB insertion."""
    fetcher = MospiCpiAirfareFetcher()
    series = fetcher.fetch_all()

    now = datetime.now(timezone.utc)
    records = []

    for period, data in series.items():
        year, month = period.split("-")
        records.append({
            "period": period,
            "data_date": date(int(year), int(month), 15),  # Mid-month reference
            "airfare_index": data["airfare_index"],
            "transport_index": data["transport_index"],
            "general_index": data["general_index"],
            "inflation_yoy": data["inflation_yoy"],
            "source": "MOSPI_CPI",
            "source_url": "https://esankhyiki.mospi.gov.in",
            "cpi_code": AIRFARE_CODE,
            "base_year": "2024=100",
            "fetched_at": now,
            "created_at": now,
        })

    return records
