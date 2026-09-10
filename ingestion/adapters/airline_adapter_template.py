"""
AirIndex India — Real Airline Adapter TEMPLATE
=================================================
This is a *skeleton*, not a working scraper. It shows the required
structure, guardrails, and compliance checks every real airline/OTA
adapter must implement, per spec section 2 & 12:

    "Follow ethical and legal scraping practices. Respect robots.txt,
    rate limits and website terms. Do not bypass CAPTCHA, authentication,
    access controls, anti-bot systems or use stealth techniques."
    "If a source cannot currently be accessed, the system must clearly
    show SOURCE UNAVAILABLE rather than pretending that live data was
    collected."

Why this ships as a template rather than a finished scraper
---------------------------------------------------------------
- Airline booking-flow HTML/DOM structure changes frequently and differs
  per airline; hardcoding selectors here would be stale on day one and
  is exactly the kind of site-specific reverse-engineering that needs a
  human on the team to review against each airline's current
  robots.txt and Terms of Service before it is ever pointed at a live
  site.
- **This was actually checked, not assumed**: see
  docs/ROBOTS_TXT_FINDINGS.md for the real robots.txt of IndiGo, Air
  India Express, and SpiceJet, fetched live during this build. All
  three explicitly disallow bot access to their booking/fare-search
  paths (IndiGo: `/booking/*`, `/book/*`; Air India Express:
  `/flight-availability`; SpiceJet: `/api/v1`, `/externalBooking`).
  That means a compliant scraper literally cannot be built against
  these three sites' own search flows — this isn't a hypothetical
  caveat, it's what their robots.txt says today. Air India and Akasa
  Air's robots.txt weren't retrievable in this session (see that doc)
  and need direct verification before any adapter work starts on them.
- Given the above, the higher-value next step for real data isn't
  writing more of this template — it's pursuing OTA partner/affiliate
  APIs or DGCA's public statistics (see docs/ROBOTS_TXT_FINDINGS.md's
  "Overall implication" section).

What IS implemented here
----------------------------
- robots.txt fetch + parse + allow/deny check (uses urllib's built-in
  RobotFileParser — no bypass logic of any kind).
- A token-bucket rate limiter so a real adapter can't hammer a site.
- The exact BaseSourceAdapter contract (collect / to_common_format),
  so once a team member fills in the legally-reviewed, site-specific
  Playwright selectors, it drops straight into the ingestion
  orchestrator alongside DemoAdapter with zero core-system changes.
- A worked example structure for a single fictional route/date search,
  clearly marked with TODOs where site-specific implementation goes.

To activate a real adapter for a given airline
--------------------------------------------------
1. Confirm robots.txt allows the specific search-results paths you intend
   to hit, and read the site's Terms of Service regarding automated
   access.
2. Fill in `_search_selectors` and `_parse_results` for that airline.
3. Set reasonable `min_delay_seconds` for that airline (start
   conservative, e.g. several seconds between requests).
4. If the site requires login, JS challenges, or presents a CAPTCHA to
   proceed — STOP. Per spec section 2/12 this adapter must not attempt
   to solve or bypass it. Raise SourceUnavailableError instead and,
   if a legitimate partner/affiliate API exists, integrate that instead
   of scraping.
"""

from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

import pandas as pd

from ingestion.adapters.base import BaseSourceAdapter, CollectionRequest, SourceUnavailableError


class RateLimiter:
    """Simple minimum-delay-between-requests limiter (a token bucket of
    size 1). Real adapters should tune min_delay_seconds conservatively
    and honor any Crawl-delay directive found in robots.txt."""

    def __init__(self, min_delay_seconds: float):
        self.min_delay_seconds = min_delay_seconds
        self._last_request_ts: float | None = None

    def wait(self):
        if self._last_request_ts is not None:
            elapsed = time.monotonic() - self._last_request_ts
            remaining = self.min_delay_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_ts = time.monotonic()


def check_robots_txt(base_url: str, path: str, user_agent: str = "AirIndexIndiaBot") -> tuple[bool, float | None]:
    """Returns (is_allowed, crawl_delay_seconds_or_None). Uses Python's
    stdlib RobotFileParser — reads and respects robots.txt only, no
    circumvention of any kind. Requires network access to fetch
    robots.txt, which this offline build sandbox does not have; a real
    deployment must run this check live before every ingestion run,
    not just once at adapter-authoring time (robots.txt can change)."""
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as e:
        # If robots.txt can't be fetched/parsed, fail closed: treat as
        # not allowed rather than assuming permission.
        raise SourceUnavailableError(
            source_name=parsed.netloc,
            reason=f"could_not_fetch_robots_txt: {e}",
        )
    allowed = rp.can_fetch(user_agent, path)
    delay = rp.crawl_delay(user_agent)
    return allowed, delay


@dataclass
class AirlineAdapterConfig:
    airline_name: str
    base_url: str
    min_delay_seconds: float = 5.0
    user_agent: str = "AirIndexIndiaBot/1.0 (+https://example.gov.in/airindex; contact: data-team@example.gov.in)"


class AirlineAdapterTemplate(BaseSourceAdapter):
    """Concrete airline adapters (IndiGoAdapter, AirIndiaAdapter, ...)
    should subclass this, set source_name/source_type, and implement
    `_search_selectors` / `_parse_results` for their specific site."""

    source_type = "LIVE_SCRAPE"

    def __init__(self, config: AirlineAdapterConfig):
        self.config = config
        self.source_name = config.airline_name
        self.rate_limiter = RateLimiter(config.min_delay_seconds)

    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        rows = []
        search_path = "/flights/search"  # TODO: real search path for this airline

        allowed, crawl_delay = check_robots_txt(self.config.base_url, search_path, self.config.user_agent)
        if not allowed:
            raise SourceUnavailableError(self.source_name, "disallowed_by_robots_txt")
        if crawl_delay:
            self.rate_limiter.min_delay_seconds = max(self.rate_limiter.min_delay_seconds, crawl_delay)

        try:
            for route in request.routes:
                for window in request.booking_windows:
                    self.rate_limiter.wait()
                    result = self._search_one(route, window, request.as_of)
                    if result is not None:
                        rows.extend(result)
        except SourceUnavailableError:
            raise
        except Exception as e:
            # Any unexpected failure (site structure changed, JS
            # challenge/CAPTCHA encountered, timeout, etc.) degrades to
            # SOURCE UNAVAILABLE — never partially-fabricated data.
            raise SourceUnavailableError(self.source_name, f"collection_failed: {e}")

        if not rows:
            raise SourceUnavailableError(self.source_name, "no_results_returned")

        return pd.DataFrame(rows)

    def _search_one(self, route: str, booking_window_days: int, as_of: date):
        """TODO (per-airline, after legal/robots.txt review): use
        Playwright to load the search results page for `route` with a
        travel date of as_of + booking_window_days, wait for the results
        to render, and hand off to `_parse_results`.

        Guardrails that MUST remain true in any real implementation:
          - No solving/bypassing of CAPTCHAs or bot-challenge pages —
            if one appears, treat it as SourceUnavailableError.
          - No credential-based login flows.
          - No stealth/fingerprint-spoofing plugins.
          - Respect `self.rate_limiter` between every page load.
        """
        raise NotImplementedError(
            "Fill in with a legally-reviewed, site-specific Playwright "
            "flow for this airline before use."
        )

    def _parse_results(self, page_content) -> list[dict]:
        """TODO: parse the rendered results into a list of dicts using
        the canonical-ish field names (origin, destination, airline,
        flight_number, travel_date, base_fare, taxes_fees, total_fare,
        fare_class, availability_status)."""
        raise NotImplementedError

    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        # If _parse_results already emits canonical-ish field names,
        # this can just return raw_df unchanged, as DemoAdapter does.
        return raw_df
