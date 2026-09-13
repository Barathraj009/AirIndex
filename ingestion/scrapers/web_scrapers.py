"""
Concrete web-scraper adapters for the 11 sources named in the spec.

Every adapter TODAY is honestly UNAVAILABLE: see ingestion/scrapers/sources.py
for the live robots.txt findings that justify each status. Each subclass
wires its spec and, when a compliant live path is later added (a partner
fare API, an officially-sanctioned feed, or a legally-reviewed scrape of a
site that ALLOWS the fare path), `_collect_compliant()` is the single
method to implement — the robots gate and canonical mapping are already in
place.

Until then these adapters raise SourceUnavailableError on collect(), which
the orchestrator records as a SOURCE_UNAVAILABLE run — exactly the honest
behavior the spec requires ("mark UNAVAILABLE sources honestly").

The demo fallback (DEMO_GENERATOR + the clearly-labeled demo fixtures) is
independent of these adapters and is what the dashboard shows when a
source's live status is UNAVAILABLE.
"""

from __future__ import annotations

from ingestion.adapters.base import CollectionRequest, SourceUnavailableError  # noqa: F401 (re-export for subclass use)
from ingestion.scrapers.base import BaseWebScraper
from ingestion.scrapers.sources import spec_for

import pandas as pd  # noqa: F401 (type annotation for _collect_compliant)


def _make_scraper(source_name: str):
    """Build a base class pinned to one registry spec."""

    class _Scraper(BaseWebScraper):
        def __init__(self, **kwargs):
            super().__init__(spec_for(source_name), **kwargs)

        def _collect_compliant(self, request: CollectionRequest) -> pd.DataFrame:
            # No compliant live path exists yet for this source (see the
            # registry reason). Raising honestly is the required behavior;
            # a future partner-API integration replaces this method only.
            spec = self.spec
            raise SourceUnavailableError(
                spec.source_name,
                f"no_compliant_live_path: {spec.reason}",
            )

    _Scraper.__name__ = f"{source_name}Scraper"
    _Scraper.__qualname__ = _Scraper.__name__
    _Scraper.source_name = source_name
    return _Scraper


IndigoWebScraper = _make_scraper("INDIGO_WEB")
AirIndiaWebScraper = _make_scraper("AIR_INDIA_WEB")
AirIndiaExpressWebScraper = _make_scraper("AIR_INDIA_EXPRESS_WEB")
AkasaWebScraper = _make_scraper("AKASA_WEB")
SpiceJetWebScraper = _make_scraper("SPICEJET_WEB")

MakeMyTripWebScraper = _make_scraper("MAKEMYTRIP_WEB")
YatraWebScraper = _make_scraper("YATRA_WEB")
EaseMyTripWebScraper = _make_scraper("EASEMYTRIP_WEB")
CleartripWebScraper = _make_scraper("CLEARTRIP_WEB")
IxigoWebScraper = _make_scraper("IXIGO_WEB")
GoibiboWebScraper = _make_scraper("GOIBIBO_WEB")


# Mapping used by the ingest orchestrator / status endpoints.
WEB_SCRAPER_REGISTRY = {
    "INDIGO_WEB": IndigoWebScraper,
    "AIR_INDIA_WEB": AirIndiaWebScraper,
    "AIR_INDIA_EXPRESS_WEB": AirIndiaExpressWebScraper,
    "AKASA_WEB": AkasaWebScraper,
    "SPICEJET_WEB": SpiceJetWebScraper,
    "MAKEMYTRIP_WEB": MakeMyTripWebScraper,
    "YATRA_WEB": YatraWebScraper,
    "EASEMYTRIP_WEB": EaseMyTripWebScraper,
    "CLEARTRIP_WEB": CleartripWebScraper,
    "IXIGO_WEB": IxigoWebScraper,
    "GOIBIBO_WEB": GoibiboWebScraper,
}