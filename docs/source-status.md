# Scraper Source Status (live findings, 2026-09)

Status mapping: `UNAVAILABLE` everywhere today — there is **no compliant
live path** for any of the 11 sources. Each adapter exists, is registered,
and re-checks robots.txt at runtime (fail-closed), but will honestly report
`SOURCE_UNAVAILABLE` in the pipeline. The daily compliance job re-verifies
these findings automatically.

Airline findings are recorded in [ROBOTS_TXT_FINDINGS.md](ROBOTS_TXT_FINDINGS.md);
OTA findings below were re-verified live during this build.

| Source        | Category | Status       | Live finding (robots.txt / edge)                                | Fare-search path under scrutiny      |
|---------------|----------|--------------|-----------------------------------------------------------------|--------------------------------------|
| MakeMyTrip    | OTA      | UNAVAILABLE  | Disallows `/flight/search*`, `/flights/get-fare-calendar-block.html`, `/air/*` | `/flight/search`                     |
| Yatra         | OTA      | UNAVAILABLE  | Disallows `/flights-india-vx/`, `/travel-beta/cheap-air-tickets`, app paths  | `/flights-india-vx/`                 |
| EaseMyTrip    | OTA      | UNAVAILABLE  | Disallows `/flight-search/listing*` (the fare results path)       | `/flight-search/listing`             |
| Cleartrip     | OTA      | UNAVAILABLE  | Disallows `/flights/search*`, `/flights/international/search`, `/api/` | `/flights/search`                    |
| ixigo         | OTA      | UNAVAILABLE  | Disallows `/flights/search`, `/search/result/`, `/api/`, `/trains/v1/search/` | `/flights/search`                    |
| Goibibo       | OTA      | UNAVAILABLE  | Disallows `/flights/*?*` (parameterised flight pages), `/flights/new/` | `/flights/search`                    |
| IndiGo        | Airline  | UNAVAILABLE  | Disallows `/booking/*`, `/book/*`, `/search.html`, `/check-in/*`  | `/booking/bookingTypes`              |
| Air India     | Airline  | UNAVAILABLE  | `airindia.com/robots.txt` edge-blocked (HTTP 000, bot and browser UA) | `/booking`                           |
| AI Express    | Airline  | UNAVAILABLE  | Disallows `/flight-availability` (the results path), `/retro-claim` | `/flight-availability`               |
| Akasa Air     | Airline  | UNAVAILABLE  | robots.txt permissive (HTTP 200, no Disallow) but the booking flow is an SPA over a private JSON API with CAPTCHA-grade protection | `/book-flight-tickets`               |
| SpiceJet      | Airline  | UNAVAILABLE  | Disallows `/api/v1`, `/public/`, `/externalBooking` (the booking API) | `/api/v1`                            |

## Why "adapter exists but UNAVAILABLE" is correct

The spec requires honest labeling and an actual compliant access method
before a source is marked `LIVE`. Building an adapter that bypasses a
disallow rule or anti-bot wall would violate robots.txt/ToS and the
spec's compliance rules; therefore the framework ships the compliant
scaffold (robots gate, canonical mapping, orchestrator hooks) with each
source honestly `UNAVAILABLE`, plus a `DEMO_GENERATOR` fallback the
dashboard uses until a partner/affiliate API is added.

## Path to LIVE (for each source)

| Source        | Compliant path that would flip this source to LIVE                    |
|---------------|------------------------------------------------------------------------|
| All OTAs      | An officially documented/partner fare API (e.g. affiliate feed, B2B JSON endpoint accessible under ToS). |
| IndiGo / AI Express / SpiceJet / Akasa | A published schedule-and-fare feed or partner-agreement API. |
| Air India     | A robots.txt reachable at the edge + public fare API, or partner feed. |

None of these exist as of 2026-09-13; when they do, only
`_collect_compliant()` in `ingestion/scrapers/web_scrapers.py` needs to be
implemented per source.