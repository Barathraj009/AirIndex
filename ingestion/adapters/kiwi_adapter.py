"""
AirIndex India — Kiwi.com Tequila Flight Price Adapter
=======================================================
Fetches real-time domestic airfare data from Kiwi.com's Tequila API.
Free tier: 50 requests/month, no credit card required.

Data source: https://tequila.kiwi.com
API docs: https://tequila.kiwi.com/center/api
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import requests

from ingestion.adapters.base import BaseSourceAdapter, CollectionRequest, SourceUnavailableError

logger = logging.getLogger(__name__)

# Indian airport IATA codes for domestic routes
INDIAN_AIRPORTS = {
    "DEL": "Delhi",
    "BOM": "Mumbai",
    "BLR": "Bengaluru",
    "MAA": "Chennai",
    "CCU": "Kolkata",
    "HYD": "Hyderabad",
    "GOI": "Goa",
    "PNQ": "Pune",
    "COK": "Kochi",
    "AMD": "Ahmedabad",
    "ATQ": "Amritsar",
    "GAU": "Guwahati",
    "JAI": "Jaipur",
    "LKO": "Lucknow",
    "PAT": "Patna",
    "TRV": "Thiruvananthapuram",
}


class KiwiFlightAdapter(BaseSourceAdapter):
    """Fetches real domestic airfares from Kiwi.com Tequila API."""

    source_name = "KIWI_FLIGHTS"
    source_type = "LIVE_SCRAPE"

    BASE_URL = "https://api.tequila.kiwi.com"

    def __init__(self):
        self.api_key = os.getenv("KIWI_API_KEY", "")

    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        """Fetch flight prices from Kiwi.com API."""
        if not self.api_key:
            raise SourceUnavailableError(
                self.source_name,
                "KIWI_API_KEY not configured"
            )

        try:
            all_records = []

            for route in request.routes:
                origin, dest = route.split("-")

                # Skip routes with unknown airports
                if origin not in INDIAN_AIRPORTS or dest not in INDIAN_AIRPORTS:
                    continue

                try:
                    route_records = self._search_route(
                        origin, dest, request.as_of, request.booking_windows
                    )
                    all_records.extend(route_records)
                    time.sleep(0.5)  # Rate limit
                except Exception as e:
                    logger.warning(f"Error searching {route}: {e}")
                    continue

            if not all_records:
                raise SourceUnavailableError(
                    self.source_name,
                    "No flight data returned from Kiwi.com"
                )

            return pd.DataFrame(all_records)

        except SourceUnavailableError:
            raise
        except Exception as e:
            raise SourceUnavailableError(
                self.source_name,
                f"Error fetching from Kiwi.com: {e}"
            )

    def _search_route(self, origin: str, dest: str, as_of: date,
                      booking_windows: list[int]) -> list[dict]:
        """Search flights for a specific route."""
        records = []

        for days_out in booking_windows:
            fly_date = as_of + timedelta(days=days_out)

            params = {
                "fly_from": origin,
                "fly_to": dest,
                "date_from": fly_date.strftime("%d/%m/%Y"),
                "date_to": fly_date.strftime("%d/%m/%Y"),
                "flight_type": "round",  # or "oneway"
                "adults": 1,
                "curr": "INR",
                "locale": "en",
                "limit": 10,  # Top 10 cheapest
            }

            headers = {
                "apikey": self.api_key,
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"{self.BASE_URL}/v2/search",
                params=params,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            for flight in data.get("data", []):
                record = self._parse_flight(flight, origin, dest, days_out, as_of)
                if record:
                    records.append(record)

        return records

    def _parse_flight(self, flight: dict, origin: str, dest: str,
                      days_out: int, as_of: date) -> Optional[dict]:
        """Parse a single flight result."""
        try:
            price = flight.get("price", 0)
            if price <= 0:
                return None

            # Extract airline info
            airlines = flight.get("airlines", [])
            airline_name = airlines[0] if airlines else "Unknown"

            # Extract flight numbers
            route = flight.get("route", [])
            flight_number = ""
            if route:
                flight_number = route[0].get("flight_no", "")

            # Extract times
            fly_date_str = flight.get("dtime", "")
            travel_date = flight.get("local_departure", "")[:10]

            # Calculate base fare (72%) and taxes (28%)
            base_fare = price * 0.72
            taxes_fees = price * 0.28

            return {
                "origin": origin,
                "destination": dest,
                "airline": airline_name,
                "flight_number": str(flight_number),
                "travel_date": travel_date,
                "collection_timestamp": datetime.utcnow().isoformat(),
                "booking_window_days": days_out,
                "fare_class": "ECONOMY",
                "base_fare": round(base_fare, 2),
                "taxes_fees": round(taxes_fees, 2),
                "total_fare": round(price, 2),
                "currency": "INR",
                "availability_status": "AVAILABLE",
                "source": self.source_name,
                "source_type": self.source_type,
                "data_quality_status": "VALID",
                "quality_flags": f"kiwi_id={flight.get('id', '')}",
            }

        except (KeyError, TypeError, ValueError) as e:
            logger.debug(f"Error parsing flight: {e}")
            return None

    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Data is already in common format."""
        return raw_df
