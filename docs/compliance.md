# Scraping Compliance Policy & Decision Log

This document is the living record of why each source is labeled the way
it is, and of the rules every adapter in this repo is bound by.

## Rules (binding)

1. **robots.txt is checked before every collection** and the check is
   fail-closed: if robots.txt is unreachable or unparseable, the source is
   treated as NOT crawlable for the requested path. (RE: RE-264 pre
   commit) See `ingestion/scrapers/robots.py`.
2. **No bypassing anti-bot protection of any kind**, including CAPTCHAs,
   login walls, fingerprinting evasion, or changing the User-Agent to
   disguise scripted traffic.
3. **No tolerated-policy scraping** of robots-disallowed paths; the only
   adjustments are the documented on-edge `Timeout`/rate-limit handling in
   the shared adapter base (already existing) and the compliance guard.
4. **Never fabricate data.** If a source cannot be reached compliantly,
   return `SOURCE_UNAVAILABLE` with the reason. The demo generator is the
   *only* synthetic data, and it is always labeled `DEMO`/`SOURCE_TYPE
   DEMO_SIMULATED`.
5. **User-Agent identifies the project.** `AirIndexIndiaBot/1.0`
   (`settings.scraper_user_agent`).
6. **Rate limiting** honours robots.txt `Crawl-delay` when present and the
   configured `scraper_min_delay_seconds` floor.
7. **Playwright** is only used for rendering explicitly allowed pages as a
   civil alternative to against-wall JavaScript — never to obfuscate bot
   behavior.
8. **Partnership path:** a source may only be marked `LIVE` when there is a
   genuine compliant method (partner/affiliate API, official feed, or a
   site that allows the fare-search path), implemented and tested.

## Decision log

- **2026-09-05 — IndiGo, Air India Express, SpiceJet.** Live robots.txt
  checks disallow the entire fare/booking flows. All three labeled
  `UNAVAILABLE`.
- **2026-09-06 — Air India.** `airindia.com/robots.txt` is edge-blocked
  (HTTP 000 for bot and browser UAs). Cannot comply → `UNAVAILABLE`.
- **2026-09-06 — Akasa Air.** robots.txt permismssive (200, no Disallow),
  but the booking flow is an SPA over a private JSON API behind
  CAPTCHA-grade protection; no sane compliant direct path → `UNAVAILABLE`.
- **2026-09-13 — MakeMyTrip, Yatra, EaseMyTrip, Cleartrip, ixigo,
  Goibibo.** Live robots.txt re-verified; every OTA disallows its fare
  search/results paths (and several disallow `/api/` entirely). All six
  `UNAVAILABLE`.
- **2026-09-13 — Framework shipped.** Adapters registered with honest
  status, robots gate + canonical mapping in place, `DEMO_GENERATOR`
  fallback for the dashboard. No source crossed the `LIVE` line because
  no compliant path exists as of this date.

## Re-verification

`run_scraper_compliance_check` (scheduler, daily 06:30 UTC) re-fetches
robots.txt for all 11 sources (cache bypass) and logs non-compliant
verdicts to `scraper_errors`. The Scraper Monitor surfaces these live so a
flapping robots.txt is visible in hours, not weeks.