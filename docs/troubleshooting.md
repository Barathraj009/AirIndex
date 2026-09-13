# Scraping Troubleshooting

Common symptoms and fixes for the web-scraping framework.

## Every source reports UNAVAILABLE — is something broken?

No. That is the intended, honest state. As of 2026-09-13 none of the 11
sources has a compliant live path (robots.txt disallows the fare-search
paths). See [source-status.md](source-status.md) and
[compliance.md](compliance.md).

To confirm the reason a specific source is down, call the Scraper Monitor:

```bash
curl -H "Authorization: Bearer $TOKEN" /api/scrapers/status
# add ?force_robots_check=1 to trigger a live robots.txt re-fetch
```

`last_failure_reason` and `scraper_errors` rows explain the verdict.

## The daily compliance job doesn't seem to run

- It runs from `run_scraper_compliance_check` on the APScheduler at
  06:30 UTC. In production it runs inside the web process lifespan, so a
  restart is enough to pick up new scheduler jobs.
- If the environment is `test`, the scheduler is disabled by design.
- Check `REFRESH_OUTCOMES["scraper_compliance"]` via the existing refresh
  diagnostics endpoints to see the last run and error.

## A source's robots.txt appears to have changed but the monitor still
## shows the old verdict

The in-process cache is valid for one hour, and `/api/scrapers` does not
hit the network. Use `GET /api/scrapers/status?force_robots_check=1` for a
live (cache-bypassing) verdict.

## Adapter raises `SourceUnavailableError` even with `force_robots_check`

This is correct behavior when the bots rule disallows the path. If you
have evidence a source now permits crawling **and** you have a compliant
path to implement, update the `ScraperSpec` status to `LIVE` and implement
`_collect_compliant()` — never weaken the robots gate instead.

## `alembic check` reports drift on the new tables

Run `alembic upgrade head` first. The index names on `scraper_errors` /
`fare_searches` must match SQLAlchemy's default convention
(`ix_<table>_<column>` = `ix_scraper_errors_source_name` and
`ix_fare_searches_source_name`); the migration 0007 uses exactly those.

## The frontend Scraper Monitor is empty

- `GET /api/scrapers` requires the `view_scraping_monitor` permission;
  without a token you'll get 401.
- `/api/scrapers/runs` filters to rows whose `data_source_id` maps to one
  of the 11 source names. Until a run happens the "Recent Scraper Runs"
  card shows the empty state.
- Run `scripts/seed_database.py` if the 11 source rows are missing.

## Postgres-dependent integration tests fail locally

`tests/test_api_integration.py` connects to Postgres at boot
(`airindex_test`, forcibly set). Without a local Postgres, this single
suite errors at setUpClass — not a regression. It runs in CI.