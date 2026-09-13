# Scraper Setup & Operations

How to seed, configure, run and extend the web-scraping framework.

## Prerequisites

- Python 3.11+ with the project's `requirements.txt` installed.
- A database reachable via `DATABASE_URL` (Postgres in production, sqlite
  for local verification).
- No API keys are required for the 11 web sources: they are all
  `UNAVAILABLE` by design (compliance) and never call any private API.

## 1. DB schema + state

```bash
cd backend
alembic upgrade head            # includes 0007_add_scraper_tables
```

Create the schema and seed the 11 sources plus the existing 5 data sources:

```bash
python scripts/seed_database.py   # adds the 11 as active LIVE_SCRAPE rows
```

The source rows live in `data_sources` (mapping to the spec's `sources`
table). Run tracking reuses the existing `ingestion_runs` table
(`scraper_runs`) and normalized fare rows re-use `fare_observations`
(`fare_results`). Brand-new tables added by migration `0007`:

- `scraper_errors` — per-source error log (robots verdicts, edge blocks)
- `fare_searches` — audit of fare-search request/response stats

## 2. Scheduled jobs (scheduler_service.py)

- `run_scheduled_ingestion` — every 6h (default `ingestion_schedule_cron`),
  unchanged. Runs active sources; UNAVAILABLE web sources degrade to
  `SOURCE_UNAVAILABLE` runs.
- `run_scraper_compliance_check` (new) — daily 06:30 UTC; re-fetches
  robots.txt for the 11 sources with `force=True` (cache bypass) and logs
  non-compliant verdicts into `scraper_errors`.

## 3. API endpoints (Phase 14)

| Endpoint                   | Permissions           | Notes                                                    |
|----------------------------|-----------------------|----------------------------------------------------------|
| `GET /api/scrapers`        | `view_scraping_monitor` | Registry metadata + status (no network).                 |
| `GET /api/scrapers/status` | `view_scraping_monitor` | Adds per-source last run + robots verdict; `?force_robots_check=1` re-fetches live. |
| `GET /api/scrapers/runs`   | `view_scraping_monitor` | Recent scraper runs (scoped to the 11 source names).     |
| `GET /api/fares/latest`    | `view_dashboard`      | Latest normalized VALID fare per (route, airline, travel_date). |
| `GET /api/fares/routes`    | `view_dashboard`      | Per-route fare summary (n, n_valid, min/max/avg, latest). |

## 4. Adding a NEW source (when a compliant path opens up)

1. Add a `ScraperSpec` to `ingestion/scrapers/sources.py` (honest status
   `LIVE` only when the compliant method is actually implemented).
2. Add its adapter to `ingestion/scrapers/web_scrapers.py`
   (`WEB_SCRAPER_REGISTRY`) implementing `_collect_compliant()`.
3. Re-run `scripts/seed_database.py` (idempotent) to add the data_source row.
4. Unit-test the adapter; update `docs/source-status.md`.

## 5. Local verification (offline-friendly)

```bash
# backend unit tests (no network; Postgres-dependent suite skipped locally)
PYTHONPATH=.;./backend python -m unittest discover -s tests -p "test_scraper_framework.py" -v

# alembic chain + zero-drift on sqlite
$env:DATABASE_URL="sqlite:///verify.db"; cd backend
python -m alembic upgrade head
python -m alembic check
```

## 6. Health reporting

`backend/app/services/scraper_status.py::build_status_summary` merges the
static registry, the DB run state, and (optionally) live robots verdicts
into the payload the Scraper Monitor renders. It never fabricates state —
if a source has never run, `last_run_status` is `NEVER_RUN`.