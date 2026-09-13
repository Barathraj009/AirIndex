# Web-Scraping Architecture

Compliance-first live scrapers for the 11 sources named in the scraping
spec (5 airlines + 6 OTAs), layered on top of the existing ingestion
pipeline without touching core index logic.

## Status semantics (honest labeling)

| Status       | Meaning                                                                                          |
|--------------|--------------------------------------------------------------------------------------------------|
| `LIVE`       | A compliant, working live collection method is integrated.                                        |
| `DEMO`       | Source is only reachable through the clearly-labeled demo generator (never presented as live).    |
| `MOCK`       | Test-only source used by the automated test suite.                                                |
| `UNAVAILABLE`| No compliant live path exists (robots.txt disallows the fare-search path, or the edge blocks bots). The adapter exists and re-checks robots.txt at runtime but honestly returns `SOURCE_UNAVAILABLE`. |

Today **all 11 sources are `UNAVAILABLE`** — documented per source in
[source-status.md](source-status.md) and backed by live robots.txt
findings (2026-09) in [ROBOTS_TXT_FINDINGS.md](ROBOTS_TXT_FINDINGS.md).

## Layering

```
ingestion/scrapers/
  sources.py       SOURCE_REGISTRY: 11 ScraperSpec entries (metadata + honest status)
  robots.py        Fail-closed robots.txt guard (RobotsTxtPolicy, 1h cache, force bypass)
  fare_model.py    FareRecord / STANDARD_FARE_COLUMNS / to_canonical_columns() mapping
  base.py          BaseWebScraper(BaseSourceAdapter): compliance gate + demo fallback hook
  web_scrapers.py  11 concrete adapters wired to their spec + WEB_SCRAPER_REGISTRY

backend/app/
  services/scraper_status.py        health-report builder (registry + DB run state + verdicts)
  services/scheduler_service.py     daily compliance re-check job (Phase 13)
  api/routers/scrapers.py           GET /api/scrapers, /api/scrapers/status, /api/scrapers/runs
  api/routers/fares.py              + /api/fares/latest, /api/fares/routes (Phase 14)
  models/scraping.py                ScraperError, FareSearch (2026-09-13, migration 0007)
```

The adapters plug into `ingestion_runner._adapter_registry()` with zero
core-system changes: each source registers under its `source_name`, and
`collect_from_sources()` treats a raised `SourceUnavailableError` as an
honest `SOURCE_UNAVAILABLE` run (existing behavior).

## How a real collection works (the day a compliant path exists)

1. `BaseWebScraper.collect()` — compliance gate:
   - if the spec is administratively `UNAVAILABLE`/`MOCK` and no
     `force_robots_check` flag is set, it fails closed immediately;
   - otherwise it performs a live robots.txt check for the source's
     `fare_search_path`. Disallowed/unreachable → `SourceUnavailableError`.
2. Allowed → `_collect_compliant(request)` — the source-specific method.
   Today every source keeps this raising honestly, since no compliant path
   exists yet. Implementing a partner/affiliate API later only requires
   replacing this one method.
3. The raw frame is mapped with `FareRecord`/`to_canonical_columns()`
   onto the pipeline's `CANONICAL_COLUMNS`, with `source`/`source_type`
   set for provenance and a 72/28 base/tax split only when a source
   returns just a total (never fabricated — it is data-processing's
   existing documented convention).

## Security / compliance invariants

- Fail-closed: an unreachable robots.txt means "do not crawl", with the
  verdict surfaced as the run's failure reason.
- No bypassing of CAPTCHA, login walls, or anti-bot protections, ever.
- Playwright is only used for compliant rendering, never to mask traffic.
- No credentials or secret tokens are stored in the repository.

See [compliance.md](compliance.md) for the policy and decision log.