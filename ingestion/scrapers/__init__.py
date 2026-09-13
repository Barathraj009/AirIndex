"""
AirIndex India — Real-Time Web Scraping Framework
==================================================
Compliance-first scraper framework for the live fare sources named in the
AirIndex web-scraping spec: five Indian airlines (IndiGo, Air India,
Air India Express, Akasa Air, SpiceJet) and six OTAs (MakeMyTrip, Yatra,
EaseMyTrip, Cleartrip, ixigo, Goibibo).

Every scraper here is built around the SAME contract as the existing
ingestion package (ingestion/adapters/base.py): `collect()` returns raw
observations or raises `SourceUnavailableError`, and `to_common_format()`
maps to the canonical schema consumed by
backend/app/services/data_processing.run_pipeline().

Unlike the demo/GDS/Kiwi adapters, these adapters are deliberately
compliance-gated: each site's robots.txt is checked (fail-closed) before
any collection, and the honest LIVE / DEMO / MOCK / UNAVAILABLE status is
tracked per source. See docs/source-status.md for the live findings.
"""

from ingestion.scrapers.fare_model import STANDARD_FARE_COLUMNS, FareRecord
from ingestion.scrapers.sources import SOURCE_REGISTRY, ScraperSpec
from ingestion.scrapers.robots import RobotsTxtPolicy

__all__ = [
    "STANDARD_FARE_COLUMNS",
    "FareRecord",
    "SOURCE_REGISTRY",
    "ScraperSpec",
    "RobotsTxtPolicy",
]