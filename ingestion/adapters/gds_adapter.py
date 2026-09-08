"""Google Flights (via RapidAPI) — Live GDS/Fare Adapter.

Fetches one-way domestic Indian fares from Google Flights' price calendar
through RapidAPI. Each route (origin -> destination) is queried once, and
results are filtered to exact travel dates that match the requested booking
windows.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.data_processing import CANONICAL_COLUMNS  # noqa: E402
from ingestion.adapters.base import (  # noqa: E402
    BaseSourceAdapter,
    CollectionRequest,
    SourceUnavailableError,
)

logger = logging.getLogger(__name__)

API_URL = "https://google-flights8.p.rapidapi.com/api/flights/getPriceCalendar"
API_HOST = "google-flights8.p.rapidapi.com"


class GdsAdapter(BaseSourceAdapter):
    source_name = "GOOGLE_FLIGHTS_API"
    source_type = "LIVE_SCRAPE"

    @staticmethod
    def _parse_route(route_str: str) -> tuple[str, str]:
        parts = route_str.split("-")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise ValueError(f"Invalid route format: {route_str!r}")
        return parts[0].strip().upper(), parts[1].strip().upper()

    @staticmethod
    def _build_headers() -> dict[str, str]:
        api_key = os.environ.get("RAPIDAPI_KEY")
        if not api_key:
            raise SourceUnavailableError(
                "GOOGLE_FLIGHTS_API", "RAPIDAPI_KEY not configured"
            )
        user_agent = os.environ.get(
            "SCRAPER_USER_AGENT", "AirIndexIndiaBot/1.0"
        )
        return {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": API_HOST,
            "User-Agent": user_agent,
        }

    def _parse_flight_day(
        self,
        item: dict,
        origin: str,
        destination: str,
        collection_date: date,
        valid_dates: set[str],
    ) -> dict | None:
        date_str = item.get("date") or item.get("travel_date") or item.get("departureDate") or ""
        if not date_str:
            return None

        normalized_date = date_str[:10]
        if normalized_date not in valid_dates:
            return None

        price_raw = item.get("price")
        if price_raw is None:
            price_raw = item.get("totalFare") or item.get("fare") or item.get("minPrice")
        if price_raw is None:
            return None

        if isinstance(price_raw, dict):
            total_fare = price_raw.get("low") or price_raw.get("min") or price_raw.get("price")
        else:
            total_fare = price_raw

        if total_fare is None:
            return None
        total_fare = float(total_fare)
        if total_fare <= 0:
            return None

        travel_date = pd.to_datetime(normalized_date).date()
        booking_window = (travel_date - collection_date).days

        airlines = item.get("airlines") or item.get("airline") or []
        if isinstance(airlines, str):
            airlines = [airlines]
        airline = airlines[0] if airlines else None

        return {
            "observation_id": None,
            "origin": origin,
            "destination": destination,
            "airline": airline,
            "flight_number": None,
            "travel_date": travel_date,
            "collection_timestamp": collection_date,
            "booking_window_days": booking_window,
            "fare_class": "ECONOMY",
            "base_fare": total_fare,
            "taxes_fees": np.nan,
            "total_fare": total_fare,
            "currency": "INR",
            "availability_status": "AVAILABLE",
            "source": self.source_name,
            "source_type": self.source_type,
            "data_quality_status": "VALID",
            "quality_flags": "",
        }

    def _handle_http_error(self, exc: httpx.HTTPStatusError, route_str: str) -> None:
        code = exc.response.status_code
        host = API_HOST

        if code == 429:
            raise SourceUnavailableError(
                self.source_name,
                f"rate_limit_exceeded: {host} (free tier quota exhausted; retry later)",
            ) from exc
        if code == 403:
            raise SourceUnavailableError(
                self.source_name, "not_subscribed_or_endpoint_not_in_plan"
            ) from exc
        if code == 401:
            raise SourceUnavailableError(
                self.source_name, "invalid_api_key"
            ) from exc
        raise SourceUnavailableError(
            self.source_name, f"HTTP {code}"
        ) from exc

    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        headers = self._build_headers()

        if not request.booking_windows:
            raise SourceUnavailableError(
                self.source_name, "No booking windows specified"
            )

        min_days = min(request.booking_windows)
        max_days = max(request.booking_windows)
        date_from = request.as_of + timedelta(days=min_days)
        date_to = request.as_of + timedelta(days=max_days)

        valid_dates: set[str] = {
            (request.as_of + timedelta(days=bw)).isoformat()
            for bw in request.booking_windows
        }

        all_rows: list[dict] = []

        try:
            client = httpx.Client(timeout=30.0)
        except Exception as exc:
            raise SourceUnavailableError(
                self.source_name, f"Failed to create HTTP client: {exc}"
            ) from exc

        with client:
            for idx, route_str in enumerate(request.routes):
                try:
                    origin, destination = self._parse_route(route_str)
                except ValueError as exc:
                    logger.warning("Skipping route %s: %s", route_str, exc)
                    continue

                params = {
                    "origin": origin,
                    "destination": destination,
                    "fromDate": date_from.strftime("%d/%m/%Y"),
                    "toDate": date_to.strftime("%d/%m/%Y"),
                }

                logger.info(
                    "Fetching price calendar %s -> %s  (dates %s..%s)",
                    origin, destination,
                    params["fromDate"], params["toDate"],
                )

                try:
                    response = client.get(
                        API_URL, headers=headers, params=params
                    )
                    if response.status_code != 200:
                        self._handle_http_error(
                            response.raise_for_status(), route_str
                        )
                    body = response.json()
                except SourceUnavailableError:
                    raise
                except httpx.HTTPStatusError as exc:
                    self._handle_http_error(exc, route_str)
                except httpx.RequestError as exc:
                    logger.error(
                        "Network error for route %s: %s", route_str, exc
                    )
                    raise SourceUnavailableError(
                        self.source_name, f"network_error: {exc}"
                    ) from exc
                except Exception as exc:
                    logger.error(
                        "Unexpected error for route %s: %s", route_str, exc
                    )
                    raise SourceUnavailableError(
                        self.source_name, f"HTTP {getattr(exc, 'response', None) and exc.response.status_code or 'unknown'}"
                    ) from exc

                flights = body.get("flights") or body.get("data") or []
                if isinstance(flights, dict):
                    flights = list(flights.values())

                logger.info(
                    "Got %d flight-day entries for %s -> %s",
                    len(flights), origin, destination,
                )

                for item in flights:
                    try:
                        row = self._parse_flight_day(
                            item, origin, destination,
                            request.as_of, valid_dates,
                        )
                        if row is not None:
                            all_rows.append(row)
                    except Exception as exc:
                        logger.warning(
                            "Failed to parse flight-day entry %s: %s",
                            item, exc,
                        )

                if idx < len(request.routes) - 1:
                    time.sleep(0.5)

        if not all_rows:
            logger.warning(
                "No fare observations collected across %d route(s)",
                len(request.routes),
            )
            return pd.DataFrame(columns=CANONICAL_COLUMNS)

        df = pd.DataFrame(all_rows)
        logger.info(
            "Collected %d total fare observations from GOOGLE_FLIGHTS_API",
            len(df),
        )
        return df

    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        return raw_df
