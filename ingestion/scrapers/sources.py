"""
Scraper source registry — the 11 web sources the scraping spec names,
with their honest LIVE / DEMO / MOCK / UNAVAILABLE status and the
compliance findings (robots.txt / Terms) that justify each status.

Status semantics (per the spec's "mark sources honestly"):
  LIVE           — a compliant, working live collection method is integrated
  DEMO           — site is only reachable through the clearly-labeled demo
                   generator (drop-in stand-in, never presented as live data)
  MOCK           — a test-only source used by the automated test-suite
  UNAVAILABLE    — no compliant live collection path exists (robots.txt
                   disallows the fare-search path, or the edge blocks bots);
                   the adapter exists and re-checks robots.txt at runtime,
                   but will honestly return SOURCE_UNAVAILABLE until / unless
                   a compliant path (e.g. a partner/affiliate API) is added.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class SourceStatus:
    LIVE = "LIVE"
    DEMO = "DEMO"
    MOCK = "MOCK"
    UNAVAILABLE = "UNAVAILABLE"


def _aug22_dgca_note() -> str:
    return (
        "DGCA-reported Aug-2026 domestic share used for demo weighting. "
        "No public fare-search API; own-site booking path disallowed by robots.txt."
    )


@dataclass(frozen=True)
class ScraperSpec:
    source_name: str
    label: str
    category: str            # "AIRLINE" | "OTA" | "API" | "DATASET" | "DEMO"
    base_url: str
    robots_url: str
    status: str
    reason: str              # short human rationale for `status`
    fare_search_path: str | None = None   # path that WOULD carry fare results
    demo_fallback: str | None = "DEMO_GENERATOR"
    mock_adapter: str | None = None
    notes: list[str] = field(default_factory=list)


# The five carriers have robots.txt findings documented in
# docs/ROBOTS_TXT_FINDINGS.md (live-fetched 2026-09-05/06). The six OTAs'
# findings were re-verified live during this build (see docs/source-status.md).
SOURCE_REGISTRY: list[ScraperSpec] = [
    ScraperSpec(
        source_name="MAKEMYTRIP_WEB",
        label="MakeMyTrip",
        category="OTA",
        base_url="https://www.makemytrip.com",
        robots_url="https://www.makemytrip.com/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="robots.txt disallows /flight/search*, /flights/get-fare-calendar-block.html and /air/*",
        fare_search_path="/flight/search",
        notes=["Live robots.txt: /flight/search* and /air/* Disallowed.",
               "Fare search is served from the JS app behind an API that is not publicly documented."],
    ),
    ScraperSpec(
        source_name="YATRA_WEB",
        label="Yatra",
        category="OTA",
        base_url="https://www.yatra.com",
        robots_url="https://www.yatra.com/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="robots.txt disallows /flights-india-vx/, /travel-beta/cheap-air-tickets and app paths",
        fare_search_path="/flights-india-vx/",
        notes=["Live robots.txt: /flights-india-vx/ and /travel-beta/cheap-air-tickets Disallowed.",
               "No public fare API; search runs inside the JS application."],
    ),
    ScraperSpec(
        source_name="EASEMYTRIP_WEB",
        label="EaseMyTrip",
        category="OTA",
        base_url="https://www.easemytrip.com",
        robots_url="https://www.easemytrip.com/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="robots.txt disallows /flight-search/listing* (the fare results path)",
        fare_search_path="/flight-search/listing",
        notes=["Live robots.txt: /flight-search/listing* Disallowed.",
               "No public fare-search API documented."],
    ),
    ScraperSpec(
        source_name="CLEARTRIP_WEB",
        label="Cleartrip",
        category="OTA",
        base_url="https://www.cleartrip.com",
        robots_url="https://www.cleartrip.com/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="robots.txt disallows /flights/search* and /flights/international/search",
        fare_search_path="/flights/search",
        notes=["Live robots.txt: /flights/search* Disallowed.",
               "No public fare-search API."],
    ),
    ScraperSpec(
        source_name="IXIGO_WEB",
        label="ixigo",
        category="OTA",
        base_url="https://www.ixigo.com",
        robots_url="https://www.ixigo.com/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="robots.txt disallows /flights/search, /search/result/ and /api/",
        fare_search_path="/flights/search",
        notes=["Live robots.txt: /flights/search and /search/result/ Disallowed.",
               "No public fare-search API."],
    ),
    ScraperSpec(
        source_name="GOIBIBO_WEB",
        label="Goibibo",
        category="OTA",
        base_url="https://www.goibibo.com",
        robots_url="https://www.goibibo.com/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="robots.txt disallows /flights/*?* (parameterised flight pages) and /flights/new/",
        fare_search_path="/flights/search",
        notes=["Live robots.txt: Disallow /flights/*?* and /flights/new/.",
               "No public fare-search API."],
    ),
    ScraperSpec(
        source_name="INDIGO_WEB",
        label="IndiGo",
        category="AIRLINE",
        base_url="https://www.goindigo.in",
        robots_url="https://www.goindigo.in/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="robots.txt disallows /booking/*, /book/* and /search.html (the fare flow)",
        fare_search_path="/booking/bookingTypes",
        notes=["Live robots.txt (2026-09-05): /booking/*, /book/*, /search.html Disallowed.",
               _aug22_dgca_note()],
    ),
    ScraperSpec(
        source_name="AIR_INDIA_WEB",
        label="Air India",
        category="AIRLINE",
        base_url="https://www.airindia.com",
        robots_url="https://www.airindia.com/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="airindia.com/robots.txt is edge-blocked (HTTP 000 for both bot and browser UA)",
        fare_search_path="/booking",
        notes=["Live check (2026-09-06): robots.txt refused at the network edge.",
               "No public fare-search API; treat the site as offline per docs/ROBOTS_TXT_FINDINGS.md."],
    ),
    ScraperSpec(
        source_name="AIR_INDIA_EXPRESS_WEB",
        label="Air India Express",
        category="AIRLINE",
        base_url="https://www.airindiaexpress.com",
        robots_url="https://www.airindiaexpress.com/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="robots.txt disallows /flight-availability (the fare-search results path)",
        fare_search_path="/flight-availability",
        notes=["Live robots.txt (2026-09-05): /flight-availability Disallowed.",
               _aug22_dgca_note()],
    ),
    ScraperSpec(
        source_name="AKASA_WEB",
        label="Akasa Air",
        category="AIRLINE",
        base_url="https://www.akasaair.com",
        robots_url="https://www.akasaair.com/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="robots.txt is permissive but the fare-search flow is behind JS/CAPTCHA-grade protection",
        fare_search_path="/book-flight-tickets",
        notes=["Live check (2026-09-06): robots.txt HTTP 200, no Disallow rules.",
               "No public fare API; booking flow is an SPA over a private JSON API."],
    ),
    ScraperSpec(
        source_name="SPICEJET_WEB",
        label="SpiceJet",
        category="AIRLINE",
        base_url="https://www.spicejet.com",
        robots_url="https://www.spicejet.com/robots.txt",
        status=SourceStatus.UNAVAILABLE,
        reason="robots.txt disallows /api/v1, /public/ and /externalBooking (the entire booking flow)",
        fare_search_path="/api/v1",
        notes=["Live robots.txt (2026-09-05): /api/v1 Disallowed.",
               "No public fare-search API; their own private API is explicitly disallowed for bots."],
    ),
]


def spec_for(source_name: str) -> ScraperSpec:
    for spec in SOURCE_REGISTRY:
        if spec.source_name == source_name:
            return spec
    raise KeyError(f"No scraper spec registered for {source_name!r}")


def all_scraper_specs() -> list[ScraperSpec]:
    return list(SOURCE_REGISTRY)