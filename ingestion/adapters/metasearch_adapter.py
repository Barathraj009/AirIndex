"""Metasearch / Google Flights Scraper Adapter — Playwright-based.

Scrapes real-time fare data from Google Flights search results. Degrades
gracefully when Playwright is not installed: the adapter can still be
imported and inspected, but `collect()` will raise SourceUnavailableError
immediately.

Respects rate limits (3 s between requests) and uses a realistic
User-Agent to minimise the chance of being blocked.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import date, datetime

import pandas as pd

from ingestion.adapters.base import (
    BaseSourceAdapter,
    CollectionRequest,
    SourceUnavailableError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Playwright import — degrade gracefully if not installed
# ---------------------------------------------------------------------------

_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright  # type: ignore[import-untyped]
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning(
        "playwright is not installed — Google Flights adapter will raise "
        "SourceUnavailableError on collect().  Install with: "
        "pip install playwright && playwright install chromium"
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_GOOGLE_FLIGHTS_SEARCH_URL = (
    "https://www.google.com/travel/flights"
    "?q=Flights+from+{origin}+to+{dest}+on+{travel_date}"
    "&curr=INR&hl=en"
)

_RATE_LIMIT_SECONDS = 3

_PLAYWRIGHT_BROWSERS_PATH = os.environ.get(
    "PLAYWRIGHT_BROWSERS_PATH", "E:\\playwright-browsers"
)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class MetasearchAdapter(BaseSourceAdapter):
    """Scrapes Google Flights via headless Chromium (Playwright).

    If Playwright is unavailable, every call to `collect()` raises
    SourceUnavailableError immediately so the orchestrator can log the
    failure and move on.
    """

    source_name = "GOOGLE_FLIGHTS"
    source_type = "LIVE_SCRAPE"

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        if not _PLAYWRIGHT_AVAILABLE:
            raise SourceUnavailableError(
                self.source_name,
                "playwright not installed",
            )

        try:
            return self._scrape_routes(request)
        except SourceUnavailableError:
            raise
        except Exception as exc:
            logger.exception("Google Flights scrape failed")
            raise SourceUnavailableError(self.source_name, str(exc)) from exc

    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        # `collect()` already returns data in canonical column order.
        return raw_df

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _scrape_routes(self, request: CollectionRequest) -> pd.DataFrame:
        all_rows: list[dict] = []
        collection_ts = datetime.now()

        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _PLAYWRIGHT_BROWSERS_PATH

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = browser.new_context(
                user_agent=_USER_AGENT,
                viewport={"width": 1366, "height": 768},
                locale="en-IN",
            )
            page = context.new_page()

            for idx, route in enumerate(request.routes):
                origin, dest = self._parse_route(route)
                if origin is None or dest is None:
                    logger.warning("Skipping malformed route: %s", route)
                    continue

                travel_date = self._resolve_travel_date(request.as_of, idx)

                url = _GOOGLE_FLIGHTS_SEARCH_URL.format(
                    origin=origin,
                    dest=dest,
                    travel_date=travel_date.isoformat(),
                )

                logger.info("Fetching %s", url)

                try:
                    page.goto(url, wait_until="networkidle", timeout=15_000)
                    # Give dynamic content a moment to settle
                    page.wait_for_timeout(3_000)

                    rows = self._extract_flights(
                        page,
                        origin=origin,
                        dest=dest,
                        travel_date=travel_date,
                        collection_ts=collection_ts,
                    )
                    all_rows.extend(rows)
                    logger.info(
                        "Extracted %d flights for %s→%s",
                        len(rows),
                        origin,
                        dest,
                    )
                except SourceUnavailableError:
                    raise
                except Exception:
                    logger.exception(
                        "Failed to extract flights for route %s→%s",
                        origin,
                        dest,
                    )
                    # Continue to next route — one failure must not kill
                    # the entire collection run.

                # Rate-limit between requests
                if idx < len(request.routes) - 1:
                    time.sleep(_RATE_LIMIT_SECONDS)

            browser.close()

        if not all_rows:
            raise SourceUnavailableError(
                self.source_name,
                "no flight data extracted from any route",
            )

        return pd.DataFrame(all_rows, columns=[
            "origin",
            "destination",
            "airline",
            "flight_number",
            "travel_date",
            "collection_timestamp",
            "booking_window_days",
            "fare_class",
            "base_fare",
            "taxes_fees",
            "total_fare",
            "currency",
            "availability_status",
        ])

    # ------------------------------------------------------------------
    # extraction helpers
    # ------------------------------------------------------------------

    def _extract_flights(
        self,
        page,
        *,
        origin: str,
        dest: str,
        travel_date: date,
        collection_ts: datetime,
    ) -> list[dict]:
        """Run JS inside the page to pull flight card data.

        Google Flights uses a complex DOM structure that changes
        frequently.  The JS below targets the most stable attributes
        (role="listitem" containers, price elements, etc.) and falls
        back to a best-effort regex scan of the page text if the
        structured selectors break.
        """

        js_extract = """
        (payload) => {
            const results = [];

            // --- Strategy 1: structured list-item extraction ---
            const cards = document.querySelectorAll(
                'li[data-ved], ul[role="list"] > li'
            );

            for (const card of cards) {
                try {
                    // Price: look for elements containing ₹ or INR amount
                    const allText = card.innerText || '';

                    // Skip cards that look like ads or info panels
                    if (allText.length < 10 || allText.length > 2000) continue;

                    // Extract price — pattern: ₹12,345 or ₹12,345 followed by details
                    const priceMatch = allText.match(/₹\\s?([\\d,]+)/);
                    if (!priceMatch) continue;
                    const price = parseInt(priceMatch[1].replace(/,/g, ''), 10);
                    if (isNaN(price) || price < 500 || price > 300000) continue;

                    // Extract airline name — usually the first meaningful line
                    const lines = allText.split('\\n').map(l => l.trim()).filter(Boolean);
                    let airline = lines[0] || '';
                    // Sometimes the first line is a time, take second
                    if (/^\\d/.test(airline) && lines.length > 1) {
                        airline = lines[1];
                    }

                    // Extract flight number — pattern like 6E 2345, SG 123, AI 456
                    const flightMatch = allText.match(
                        /\\b([A-Z0-9]{2}\\s?\\d{3,4})\\b/
                    );
                    const flightNumber = flightMatch ? flightMatch[1].replace(/\\s/, '') : '';

                    // Extract times — HH:MM pattern
                    const timeMatches = allText.match(/(\\d{1,2}:\\d{2})\\s*[–-]\\s*(\\d{1,2}:\\d{2})/);
                    const depTime = timeMatches ? timeMatches[1] : '';
                    const arrTime = timeMatches ? timeMatches[2] : '';

                    // Duration
                    const durMatch = allText.match(/(\\d+h\\s*\\d*m|\\d+h|\\d*m)/i);
                    const duration = durMatch ? durMatch[0] : '';

                    // Stops
                    const stopsMatch = allText.match(/(Direct|Nonstop|\\d+\\s*stop)/i);
                    const stops = stopsMatch ? stopsMatch[0] : '';

                    results.push({
                        airline,
                        flight_number: flightNumber,
                        price,
                        dep_time: depTime,
                        arr_time: arrTime,
                        duration,
                        stops,
                        raw_text: allText.substring(0, 500),
                    });
                } catch (e) {
                    // Skip individual card on error
                }
            }

            // --- Strategy 2: if Strategy 1 yielded nothing, try broader scan ---
            if (results.length === 0) {
                const body = document.body ? document.body.innerText : '';
                const priceBlocks = body.split(/₹/).slice(1);
                for (const block of priceBlocks.slice(0, 20)) {
                    const numMatch = block.match(/^\\s?([\\d,]+)/);
                    if (!numMatch) continue;
                    const price = parseInt(numMatch[1].replace(/,/g, ''), 10);
                    if (price < 500 || price > 300000) continue;

                    const ctx = block.substring(0, 200);
                    const airlineMatch = ctx.match(
                        /([A-Z][a-zA-Z\\s]+?)(?:\\s+\\d|\\s+Depart|\\s+₹|\\s*\\n)/
                    );

                    results.push({
                        airline: airlineMatch ? airlineMatch[1].trim() : 'Unknown',
                        flight_number: '',
                        price,
                        dep_time: '',
                        arr_time: '',
                        duration: '',
                        stops: '',
                        raw_text: block.substring(0, 500),
                    });
                }
            }

            return results;
        }
        """

        raw_flights: list[dict] = page.evaluate(
            js_extract,
            {
                "origin": origin,
                "dest": dest,
                "travelDate": travel_date.isoformat(),
            },
        )

        if not raw_flights:
            logger.warning(
                "No flights found via JS extraction for %s→%s on %s",
                origin,
                dest,
                travel_date,
            )
            return []

        return [
            self._build_row(
                raw=flight,
                origin=origin,
                dest=dest,
                travel_date=travel_date,
                collection_ts=collection_ts,
            )
            for flight in raw_flights
        ]

    # ------------------------------------------------------------------
    # row / schema helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_row(
        *,
        raw: dict,
        origin: str,
        dest: str,
        travel_date: date,
        collection_ts: datetime,
    ) -> dict:
        """Map a single raw flight dict to canonical columns."""
        booking_window = (travel_date - collection_ts.date()).days
        price = raw.get("price", 0)
        airline = raw.get("airline", "Unknown").strip()
        # Strip trailing digits that look like times accidentally captured
        airline = re.sub(r"\\s*\\d{1,2}:\\d{2}.*$", "", airline).strip() or "Unknown"

        return {
            "origin": origin,
            "destination": dest,
            "airline": airline,
            "flight_number": raw.get("flight_number") or None,
            "travel_date": travel_date,
            "collection_timestamp": collection_ts,
            "booking_window_days": max(booking_window, 0),
            "fare_class": "ECONOMY",
            "base_fare": float(price),
            "taxes_fees": 0.0,
            "total_fare": float(price),
            "currency": "INR",
            "availability_status": "AVAILABLE",
        }

    @staticmethod
    def _parse_route(route: str) -> tuple[str | None, str | None]:
        """Split 'DEL-BOM' into ('DEL', 'BOM').  Returns (None, None)
        on malformed input."""
        parts = route.upper().replace(" ", "").split("-")
        if len(parts) != 2 or not all(p.isalpha() and len(p) == 3 for p in parts):
            return None, None
        return parts[0], parts[1]

    @staticmethod
    def _resolve_travel_date(as_of: date, route_index: int) -> date:
        """Map route index to a travel date.  The first route searches
        tomorrow, subsequent routes search progressively further out
        (3, 7, 14 days) to cover a range of booking windows."""
        offsets = [1, 3, 7, 14, 21, 30]
        offset = offsets[min(route_index, len(offsets) - 1)]
        return as_of + pd.Timedelta(days=offset)
