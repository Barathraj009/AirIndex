"""Google Flights (via RapidAPI) — Live GDS/Fare Adapter.

Fetches Indian domestic fares from Google Flights' per-day price calendar
through RapidAPI (provider ``google-flights8``).  One "price graph" request
per route returns a ~90-day calendar of cheapest fares, so a single call
covers all configured booking windows (T+1 / T+7 / T+15 / T+30 / T+45).

Provider quirk handled here: when the requested centre date is close to
"today" the price-graph comes back sparse (+-3 days, every-other-day),
whereas a centre date ~30+ days out returns the full 91-day range.  We
therefore query with ``as_of + 30`` as the centre (which spans every
requested window) and only issue a second, near-date call when a window
is still missing from the response.

The provider only serves calendar prices in USD regardless of the
``currency`` request parameter, so each observation is converted to INR
using ``FX_RATE_USD_INR`` (see .env.example). A constant FX factor cancels
out in day-over-day index arithmetic, so the index and change analysis are
unaffected by the conversion choice.
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

API_URL = "https://google-flights8.p.rapidapi.com/api/v1/flights/price-graph/one-way"
API_HOST = "google-flights8.p.rapidapi.com"

DEFAULT_FX_USD_INR = 90.0


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

    @staticmethod
    def _fx_rate() -> float:
        try:
            return float(os.environ.get("FX_RATE_USD_INR", DEFAULT_FX_USD_INR))
        except (TypeError, ValueError):
            return DEFAULT_FX_USD_INR

    def _parse_flight_day(
        self,
        item: dict,
        origin: str,
        destination: str,
        collection_date: date,
        valid_dates: set[str],
    ) -> dict | None:
        date_str = item.get("departureDate") or item.get("date") or ""
        normalized_date = date_str[:10]
        if normalized_date not in valid_dates:
            return None

        price_usd = item.get("price")
        if price_usd is None:
            return None
        try:
            price_usd = float(price_usd)
        except (TypeError, ValueError):
            return None
        if price_usd <= 0:
            return None

        total_fare = round(price_usd * self._fx_rate(), 2)
        travel_date = pd.to_datetime(normalized_date).date()
        booking_window = (travel_date - collection_date).days

        return {
            "observation_id": None,
            "origin": origin,
            "destination": destination,
            "airline": "MULTI",
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
        # Query the price graph centred far enough ahead that the provider
        # returns the full 91-day calendar (it returns only a sparse +-3-day
        # sample for centres close to today). Centre at as_of+30 spans every
        # requested window (range is roughly as_of .. as_of+90).
        far_center = request.as_of + timedelta(days=30)
        near_center = request.as_of + timedelta(days=8)

        valid_dates: set[str] = {
            (request.as_of + timedelta(days=bw)).isoformat()
            for bw in request.booking_windows
        }

        def _fetch_prices(center: date, route_str: str,
                          origin: str, destination: str) -> list[dict]:
            params = {
                "origin": origin,
                "destination": destination,
                "date": center.isoformat(),
                "currency": "USD",
            }
            logger.info(
                "Fetching price graph %s -> %s  (centre %s)",
                origin, destination, center.isoformat(),
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

            prices = body.get("prices") or []
            if not prices and body.get("message"):
                raise SourceUnavailableError(
                    self.source_name,
                    f"provider_error: {body.get('message')}",
                )
            return prices

        all_rows: list[dict] = []

        try:
            client = httpx.Client(timeout=45.0)
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

                rows: list[dict] = []
                far_prices = _fetch_prices(far_center, route_str,
                                           origin, destination)
                logger.info(
                    "Got %d price-graph entries for %s -> %s (far)",
                    len(far_prices), origin, destination,
                )
                for item in far_prices:
                    try:
                        row = self._parse_flight_day(
                            item, origin, destination,
                            request.as_of, valid_dates,
                        )
                        if row is not None:
                            rows.append(row)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Failed to parse price-graph entry %s: %s",
                            item, exc,
                        )

                collected = {r["travel_date"].isoformat() for r in rows}
                missing = sorted(valid_dates - collected)
                if missing:
                    # Provider returned a sparse near-day graph; issue a
                    # second, nearer centre call to backfill missing windows.
                    logger.info(
                        "Backfilling missing windows for %s -> %s: %s",
                        origin, destination, missing,
                    )
                    near_prices = _fetch_prices(near_center, route_str,
                                                origin, destination)
                    for item in near_prices:
                        try:
                            row = self._parse_flight_day(
                                item, origin, destination,
                                request.as_of, valid_dates,
                            )
                            if row is not None and \
                                    row["travel_date"].isoformat() in missing:
                                rows.append(row)
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(
                                "Failed to parse backfill entry %s: %s",
                                item, exc,
                            )

                all_rows.extend(rows)

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