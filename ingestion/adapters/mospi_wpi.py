"""
MoSPI WPI ATF (Aviation Turbine Fuel) — Primary Data Source Adapter
===================================================================
Fetches REAL Wholesale Price Index values for Aviation Turbine Fuel
(ATF) from India's Ministry of Statistics and Programme Implementation.

Official WPI series (base 2022-23=100), item "ATF":
  - major_group_code: 1200000000 (Fuel & Power)
  - group_code:       1202000000 (Mineral Oils)
  - item_code:        1202010004 (ATF)

Source: https://esankhyiki.mospi.gov.in
API:    https://api.mospi.gov.in/api/wpi/getWpiRecords
"""

from __future__ import annotations

import logging
import ssl
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

MOSPI_API = "https://api.mospi.gov.in/api/wpi/getWpiRecords"

# WPI codes (base 2022-23)
ATF_ITEM_CODE = "1202010004"   # Aviation Turbine Fuel
ATF_GROUP_CODE = "1202000000"  # Mineral Oils
ATF_MAJOR_GROUP_CODE = "1200000000"  # Fuel & Power

WPI_BASE_YEAR = "2022-23"

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _mospi_ssl_context() -> ssl.SSLContext:
    """SSL context that tolerates MoSPI's legacy TLS renegotiation
    (same as the CPI adapter). SSL_OP_LEGACY_SERVER_CONNECT = 0x4."""
    ctx = ssl.create_default_context()
    try:
        ctx.options |= 0x4
    except (ValueError, OSError):
        pass
    return ctx


class MospiWpiAtfFetcher:
    """Fetches real WPI ATF index values from the MoSPI public API."""

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout
        self._base_url = MOSPI_API

    def _fetch_page(
        self,
        client: httpx.Client,
        base_year: str,
        item_code: str,
        year: Optional[str],
        page: int,
        limit: int,
    ) -> tuple[List[dict], dict]:
        params: Dict[str, object] = {
            "base_year": base_year,
            "item_code": item_code,
            "Format": "JSON",
            "limit": limit,
            "page": page,
        }
        if year:
            params["year"] = year
        resp = client.get(
            self._base_url,
            params=params,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("data") or [], body.get("meta_data") or {}

    def fetch_all(
        self,
        base_year: str = WPI_BASE_YEAR,
        item_code: str = ATF_ITEM_CODE,
        years: Optional[List[str]] = None,
    ) -> Dict[str, Dict]:
        """Fetch ATF WPI records and return dict keyed by period (YYYY-MM).

        Each value:
          {atf_index, inflation_mom, inflation_yoy}
        """
        records: Dict[str, Dict] = {}
        year_str = ",".join(years) if years else None

        with httpx.Client(timeout=self.timeout, verify=_mospi_ssl_context(), follow_redirects=True) as client:
            page = 1
            total_pages = 1
            while page <= total_pages:
                try:
                    rows, meta = self._fetch_page(client, base_year, item_code, year_str, page, limit=100)
                except Exception as e:
                    logger.warning(f"MoSPI WPI fetch error (page {page}): {e}")
                    break
                if not rows:
                    break
                # Latest year first; iterate in ascending order below.
                rows.sort(key=lambda r: (int(r.get("year") or 0), MONTH_MAP.get(str(r.get("month", "")).lower(), 0)))
                for rec in rows:
                    period = self._parse_period(rec)
                    if not period:
                        continue
                    records[period] = {
                        "atf_index": float(rec.get("index_value") or 0) or None,
                        "inflation_mom": None,
                        "inflation_yoy": None,
                    }
                total_pages = int(meta.get("totalPages") or 1)
                page += 1

        # Derived metrics: MoM % and YoY %.
        sorted_periods = sorted(records.keys())
        for i, p in enumerate(sorted_periods):
            year_s, month_s = p.split("-")
            if i > 0:
                prev = records.get(sorted_periods[i - 1])
                cur = records[p]["atf_index"]
                if prev and prev["atf_index"] and cur:
                    records[p]["inflation_mom"] = round(((cur - prev["atf_index"]) / prev["atf_index"]) * 100, 2)
            prev_year = f"{int(year_s) - 1}-{month_s}"
            prev_rec = records.get(prev_year)
            cur = records[p]["atf_index"]
            if prev_rec and prev_rec["atf_index"] and cur:
                records[p]["inflation_yoy"] = round(((cur - prev_rec["atf_index"]) / prev_rec["atf_index"]) * 100, 2)

        logger.info(f"MoSPI WPI: fetched {len(records)} months of ATF index data")
        return records

    def _parse_period(self, rec: dict) -> Optional[str]:
        month_name = str(rec.get("month", "")).lower()
        month_num = MONTH_MAP.get(month_name, 0)
        year = str(rec.get("year", ""))
        if month_num and year.isdigit():
            return f"{year}-{month_num:02d}"
        return None


def fetch_mospi_wpi_atf() -> List[Dict]:
    """Fetch MoSPI WPI ATF data and return as list of dicts for DB insertion."""
    fetcher = MospiWpiAtfFetcher()
    series = fetcher.fetch_all()

    now = datetime.now(timezone.utc)
    records = []

    for period, data in sorted(series.items()):
        year, month = period.split("-")
        records.append({
            "period": period,
            "data_date": date(int(year), int(month), 15),  # Mid-month reference
            "atf_index": data["atf_index"],
            "inflation_mom": data["inflation_mom"],
            "inflation_yoy": data["inflation_yoy"],
            "source": "MOSPI_WPI",
            "source_url": "https://esankhyiki.mospi.gov.in",
            "wpi_code": ATF_ITEM_CODE,
            "base_year": "2022-23",
            "fetched_at": now,
            "created_at": now,
        })

    return records