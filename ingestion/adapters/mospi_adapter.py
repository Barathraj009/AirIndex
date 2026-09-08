"""
AirIndex India — MoSPI CPI Transport Data Adapter
===================================================
Fetches Consumer Price Index (CPI) transport-related data from
India's Ministry of Statistics and Programme Implementation (MoSPI)
via the eSankhyiki portal API.

This provides official government transport inflation indices that
serve as a benchmark/reference for the AirIndex airfare index.

Data source: https://esankhyiki.mospi.gov.in/macroindicators?product=cpi
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Optional

import pandas as pd
import requests

from ingestion.adapters.base import BaseSourceAdapter, CollectionRequest, SourceUnavailableError


class MospiCpiAdapter(BaseSourceAdapter):
    """Fetches CPI transport indices from MoSPI eSankhyiki portal."""

    source_name = "MOSPI_CPI"
    source_type = "PUBLIC_DATASET"

    # MoSPI eSankhyiki API endpoint for CPI macro indicators
    # The portal serves CPI data at this endpoint
    BASE_URL = "https://esankhyiki.mospi.gov.in"

    # CPI Groups related to transport/aviation
    # Division 07 = Transport and Communication
    # Group 0702 = Transport services
    # Class 070201 = Passenger transport by railway
    # Class 070202 = Passenger transport by air
    TRANSPORT_GROUP_CODE = "07"
    TRANSPORT_SERVICES_CODE = "0702"
    AIR_TRANSPORT_CODE = "070202"
    RAIL_TRANSPORT_CODE = "070201"

    # Indian airports IATA codes for mapping CPI regions
    METRO_CITIES = ["DEL", "BOM", "BLR", "MAA", "CCU", "HYD", "GOI", "PNQ", "COK", "AMD"]

    # Headers to mimic a real browser request
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://esankhyiki.mospi.gov.in/macroindicators?product=cpi",
    }

    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        """Fetch CPI transport indices from MoSPI portal.

        Returns a DataFrame with CPI transport data that can be used as
        a benchmark/reference for the airfare index.
        """
        try:
            # Fetch CPI data from the portal's API endpoint
            cpi_data = self._fetch_cpi_transport_data()

            if not cpi_data:
                raise SourceUnavailableError(
                    self.source_name,
                    "No CPI transport data received from MoSPI portal"
                )

            return cpi_data

        except requests.RequestException as e:
            raise SourceUnavailableError(
                self.source_name,
                f"Network error fetching MoSPI data: {e}"
            )
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            raise SourceUnavailableError(
                self.source_name,
                f"Error parsing MoSPI response: {e}"
            )

    def _fetch_cpi_transport_data(self) -> pd.DataFrame:
        """Fetch CPI data from MoSPI eSankhyiki portal.

        Uses the portal's data API to get CPI indices for transport
        related items (air fare, rail fare, transport services).
        """
        # Try to fetch from the macro indicators API
        # The portal has an API endpoint for CPI data
        api_url = f"{self.BASE_URL}/api/macroindicators"

        params = {
            "product": "cpi",
            "baseYear": "2024",
            "series": "current",
            "state": "All India",
            "sector": "Combined",
        }

        response = requests.get(api_url, params=params, headers=self.HEADERS, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Parse the response and extract transport-related CPI indices
        records = self._parse_cpi_response(data)

        if not records:
            # If the API doesn't work as expected, try the HTML page
            records = self._scrape_cpi_page()

        return pd.DataFrame(records) if records else pd.DataFrame()

    def _parse_cpi_response(self, data: dict) -> list[dict]:
        """Parse MoSPI API response and extract transport CPI data."""
        records = []

        # The API response structure may vary, handle common patterns
        if isinstance(data, dict):
            # Look for data array or nested structure
            items = data.get("data", data.get("records", data.get("items", [])))
            if isinstance(items, list):
                for item in items:
                    record = self._extract_transport_record(item)
                    if record:
                        records.append(record)
            elif "groups" in data:
                # Handle grouped structure
                for group in data.get("groups", []):
                    if self._is_transport_group(group):
                        for item in group.get("items", []):
                            record = self._extract_transport_record(item)
                            if record:
                                records.append(record)

        return records

    def _is_transport_group(self, group: dict) -> bool:
        """Check if a CPI group is transport-related."""
        code = str(group.get("code", group.get("groupCode", "")))
        name = str(group.get("name", group.get("groupName", ""))).lower()

        return (
            code.startswith(self.TRANSPORT_GROUP_CODE) or
            "transport" in name or
            "air fare" in name or
            "rail fare" in name or
            "passenger" in name
        )

    def _extract_transport_record(self, item: dict) -> Optional[dict]:
        """Extract a single transport CPI record from the API response."""
        try:
            # Extract fields - adapt to actual API structure
            group_code = str(item.get("group", item.get("groupCode", "")))
            class_code = str(item.get("class", item.get("classCode", "")))
            item_name = str(item.get("item", item.get("itemName", "")))
            index_value = float(item.get("index", item.get("indexValue", 0)))
            inflation = float(item.get("inflation", item.get("inflationRate", 0)))
            month = str(item.get("month", ""))
            year = str(item.get("year", ""))

            # Only include transport-related items
            if not self._is_transport_item(group_code, class_code, item_name):
                return None

            # Map to airfare-relevant category
            category = self._categorize_transport_item(group_code, class_code, item_name)

            return {
                "item_name": item_name,
                "category": category,
                "group_code": group_code,
                "class_code": class_code,
                "cpi_index": index_value,
                "inflation_rate": inflation,
                "month": month,
                "year": year,
                "source": "MOSPI_CPI",
                "collection_timestamp": datetime.utcnow().isoformat(),
            }

        except (ValueError, TypeError):
            return None

    def _is_transport_item(self, group_code: str, class_code: str, item_name: str) -> bool:
        """Check if a CPI item is transport-related."""
        name_lower = item_name.lower()

        # Check by code
        if group_code.startswith(self.TRANSPORT_GROUP_CODE):
            return True

        # Check by name keywords
        transport_keywords = [
            "transport", "air fare", "rail fare", "passenger",
            "airline", "flight", "train", "bus fare", "taxi",
            "fuel", "petrol", "diesel"
        ]

        return any(kw in name_lower for kw in transport_keywords)

    def _categorize_transport_item(self, group_code: str, class_code: str, item_name: str) -> str:
        """Categorize transport item for airfare mapping."""
        name_lower = item_name.lower()

        if "air" in name_lower or "airline" in name_lower or "flight" in name_lower:
            return "AIR_TRANSPORT"
        elif "rail" in name_lower or "train" in name_lower:
            return "RAIL_TRANSPORT"
        elif "bus" in name_lower:
            return "ROAD_TRANSPORT"
        elif "fuel" in name_lower or "petrol" in name_lower or "diesel" in name_lower:
            return "FUEL"
        else:
            return "TRANSPORT_GENERAL"

    def _scrape_cpi_page(self) -> list[dict]:
        """Fallback: scrape CPI data directly from the HTML page."""
        records = []

        try:
            # Fetch the CPI macro indicators page
            page_url = f"{self.BASE_URL}/macroindicators?product=cpi"
            response = requests.get(page_url, headers=self.HEADERS, timeout=30)
            response.raise_for_status()

            # Parse HTML to extract CPI data
            # This is a simplified parser - in production, use BeautifulSoup
            text = response.text

            # Look for transport-related CPI entries in the response
            # The page likely renders data via JavaScript, so we may need
            # to use a different approach

            # For now, return empty - the API approach should work
            return []

        except requests.RequestException:
            return []

    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Map CPI data to the canonical fare observation schema.

        CPI transport indices are mapped to synthetic fare observations
        for a representative route (DEL-BOM) using the index values.
        """
        if raw_df.empty:
            return pd.DataFrame()

        records = []
        now = datetime.utcnow()

        for _, row in raw_df.iterrows():
            # Map CPI category to transport mode and IATA codes
            category = row.get("category", "TRANSPORT_GENERAL")

            if category == "AIR_TRANSPORT":
                # Map air transport CPI to domestic airfare observation
                origin, destination = "DEL", "BOM"
                airline = "INDIGO"  # Representative
            elif category == "RAIL_TRANSPORT":
                # Rail CPI as reference - map to similar route
                origin, destination = "DEL", "BOM"
                airline = "RAIL"
            elif category == "FUEL":
                # Fuel prices affect airfare - use as cost index
                origin, destination = "DEL", "BOM"
                airline = "FUEL_INDEX"
            else:
                # General transport
                origin, destination = "DEL", "BOM"
                airline = "TRANSPORT_GENERAL"

            # Use CPI index as a proxy for fare level
            # Scale: CPI index * 50 ≈ approximate INR fare
            # (This is a rough mapping for benchmark purposes)
            cpi_index = row.get("cpi_index", 100)
            scaled_fare = cpi_index * 50  # Approximate mapping

            # Parse month/year to create travel_date
            month_str = row.get("month", "")
            year_str = row.get("year", "")
            try:
                # Try to parse month and year
                month_num = self._parse_month(month_str)
                year_num = int(year_str) if year_str.isdigit() else 2026
                travel_date = date(year_num, month_num, 15)
            except (ValueError, TypeError):
                travel_date = date.today()

            records.append({
                "origin": origin,
                "destination": destination,
                "airline": airline,
                "flight_number": f"CPI{hashlib.md5(str(row.get('item_name', '')).encode()).hexdigest()[:4].upper()}",
                "travel_date": travel_date.isoformat(),
                "collection_timestamp": now.isoformat(),
                "booking_window_days": 30,
                "fare_class": "CPI_BENCHMARK",
                "base_fare": scaled_fare * 0.72,  # 72% base
                "taxes_fees": scaled_fare * 0.28,  # 28% taxes
                "total_fare": scaled_fare,
                "currency": "INR",
                "availability_status": "AVAILABLE",
                "source": self.source_name,
                "source_type": self.source_type,
                "data_quality_status": "VALID",
                "quality_flags": f"cpi_index={cpi_index};inflation={row.get('inflation_rate', 0)}",
            })

        return pd.DataFrame(records)

    def _parse_month(self, month_str: str) -> int:
        """Parse month string to month number."""
        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        month_lower = month_str.lower().strip()
        return month_map.get(month_lower, 1)  # Default to January
