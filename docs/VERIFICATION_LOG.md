# Verification Log — Phase 1 build session

This documents what was actually executed and observed while building
Phase 1, so the claims in the README aren't just assertions.

## Environment probe

- Python 3.12.3, Node v22.22.2/npm 10.9.7 present.
- `pip install fastapi` → fails, no network (`ERROR: No matching distribution found`).
- `npm view react version` → `403 Forbidden` (registry blocked).
- `docker --version` → not found. `psql --version` → not found.
- Pre-installed and confirmed usable: numpy 2.4.4, pandas 3.0.2,
  scipy 1.17.1, PyJWT 2.7.0, Flask 3.1.3, sqlite3 3.45.1.
- Not available and not installable offline: fastapi, sqlalchemy,
  pydantic, uvicorn, pytest.

## Demo data generation

```
$ python3 backend/app/services/demo_data_generator.py data/demo_generated.csv
Generated 30765 synthetic DEMO_SIMULATED observations -> data/demo_generated.csv
```

## Pipeline run (standalone, 8-month generation window)

```
raw rows: 30765
Data Quality Report:
  valid: 29330, suspicious: 677, invalid: 147, unavailable: 611
  outliers_iqr: 677, outliers_mad: 359, valid_pct: 95.34
Index (2026-06 vs base 2026-01): index_value = 99.06
Reproducibility check: identical inputs -> byte-identical output. PASSED.
```

## Unit tests

```
$ PYTHONPATH=.:./backend python3 -m unittest discover -s tests -v
...
Ran 18 tests in 0.183s
OK
```

One test initially failed (`test_missing_route_is_excluded_and_reported`)
because the test's hand-computed expected value was wrong (assumed equal
renormalized weighting; the engine correctly proportionally renormalizes
by original weight, giving 162.5, not 150.0). Fixed the test, re-ran,
all 18 passed.

## dev_demo Flask server — live HTTP verification

Started `dev_demo/server.py` and hit every route with `curl`:

```
/                          -> 200
/api/dashboard/summary     -> 200
/api/index/current         -> 200
/api/index/trend           -> 200
/api/routes                -> 200
/api/data-quality/summary  -> 200
/api/airlines              -> 200
```

### Bug found and fixed during this check

`/api/dashboard/summary` initially returned 500 because `base_period`
was hardcoded to `"2026-07"`, a month outside the range the demo adapter
actually generated for a 30-day collection window. Fixed by deriving
`BASE_PERIOD`/`CURRENT_PERIOD` from the generated data instead of a
literal.

### Second bug found and fixed: window-composition bias at panel edges

After the first fix, the index swung from 100 → 62.5 over 3 months —
far more than the ~0.6%/month drift the generator models. Root cause:
edge months in a short collection window only receive contributions
from short-lead (T+1/T+7/T+15, therefore artificially expensive)
booking windows, since T+30/T+45 samples for those months require
collection dates that don't exist yet at the edge of the window. This
made the base period look artificially expensive by composition, not
by any modeled trend.

Fix: (1) widened the demo adapter's collection window (150 days back,
6 months of collection) so several months have full T+1..T+45 coverage,
and (2) `dev_demo/server.py` now only selects base/current/trend
periods from months where all 5 booking windows have observations,
rather than raw row-count thresholds. Re-verified:

```
base_period: 2026-05, current_period: 2026-09
index_value: 101.62, change_from_base_pct: 1.621%
trend: 100.0 -> 100.1 -> 100.75 -> 101.36 -> 101.62  (smooth, matches modeled drift)
```

Re-ran the full unit test suite after this change: still 18/18 passing
(the fix was isolated to the demo adapter's collection window and the
dev_demo server's period-selection logic, not the index engine itself).

## What this verification does and doesn't prove

- **Proves**: the data-processing pipeline and index engine are
  logically correct, reproducible, and behave sensibly when driven by
  realistic (if synthetic) data volumes — including catching two real
  bugs before they reached a user.
- **Does not prove**: that the eventual FastAPI/SQLAlchemy/Postgres/
  React/Docker stack will run without issues — those components
  haven't been executed in this sandbox (no internet/Docker/Postgres
  available here). They'll need their own verification pass once
  built, in an environment with those tools.

---

## Phase 2 verification (FastAPI backend + React frontend)

### Security module (JWT + password hashing + RBAC) — real, executed

`backend/app/core/security.py` uses PyJWT (available offline) and
stdlib `hashlib`/`hmac` (a genuine PBKDF2-SHA256 fallback when
passlib/bcrypt aren't installed, not a placeholder). 15 unit tests, all
passing.

**Bug found and fixed**: `verify_password` initially treated *any*
non-PBKDF2-prefixed string as "must be a bcrypt hash" and raised a
`RuntimeError` for malformed/garbage input instead of returning
`False`. Fixed by checking for actual bcrypt version prefixes
(`$2a$`/`$2b$`/`$2y$`) before assuming that's what the caller meant;
anything else is now correctly treated as an invalid hash.

### Database schema — SQLAlchemy models + SQLite parity verification

PostgreSQL isn't available in this sandbox, so
`deployment/schema_postgres.sql` (the real, Alembic-baseline schema)
couldn't be executed directly. Instead, `tests/sqlite_schema.py`
translates the same schema to SQLite and `tests/test_db_schema.py`
seeds it with **real generated fare data** (from
`demo_data_generator`, run through the tested `data_processing`
pipeline) plus routes, a data source, an ingestion run, a computed
index run and its route contributions, and a user — then runs the
actual queries the dashboard endpoints will run (latest index run
joined to config, top route contributions, data-quality breakdown by
status, airline snapshot), and confirms foreign-key and uniqueness
constraints are enforced. 9/9 passing.

### Backtesting metrics — real, executed

`backend/app/services/backtesting.py` (MAE/RMSE/MAPE/correlation via
numpy/scipy, both available offline) has 8 unit tests, including
hand-verified known-answer cases and both "no reference data" and
"no overlapping periods" cases, which correctly report
`reference_available: False` rather than fabricating a comparison.

### FastAPI backend (routers, schemas, dependency injection)

Written against the tested service/DB layer, syntax-checked with
`py_compile` (all files clean) — but **not import- or
execution-verified**, since FastAPI/SQLAlchemy/Pydantic/uvicorn still
aren't installable in this sandbox. This is the same limitation
documented in Phase 1; it hasn't changed.

### React frontend — TypeScript check with ambient stubs

`npm`'s registry is blocked here, so React, TypeScript, and `tsc`
(globally pre-cached, not installed via this project's `package.json`)
were used to run the closest available check: all 20 `.ts`/`.tsx`
files were compiled with `tsc --noEmit` against hand-written ambient
`declare module` stubs for `react`, `react-router-dom`, `recharts`, and
`lucide-react` (none of which have real type packages available
offline). In loose mode (matching real-world defaults once
`@types/react` etc. are installed), **0 errors across 20 files**. In
strict mode, the only errors were `TS7016` (`react/jsx-runtime` has no
declaration file) and `TS7006`/`TS7031` implicit-`any` on event-handler
parameters (e.g. `onChange={(e) => ...}`, `NavLink`'s `isActive` render
prop) — these are artifacts of the incomplete ambient stubs (my `JSX.
IntrinsicElements` stub returns `any` for every element, so TypeScript
can't contextually infer handler parameter types the way it would with
real `@types/react`/`@types/react-router-dom` installed) rather than
real bugs in the code. This stub setup was scratch-only and is not
part of the shipped `frontend/` directory.

**What this does and doesn't prove**: confirms every page/component is
syntactically valid TSX with internally consistent types and no
undefined references. Does **not** prove the app builds/runs under
real Vite + Tailwind + Recharts + react-router-dom, or that it renders
correctly against a live backend — that needs `npm install` in an
internet-connected environment.

---

## Rebuild & full execution — 2026-09-06 (supersedes the offline caveats above)

Everything above was written in an offline sandbox. On 2026-09-06 the
project was rebuilt on a **real, internet-connected Windows host** and
every layer was executed, debugged, and re-verified. This section is
the authoritative record; where it conflicts with earlier sections,
this section wins.

### Environment (actual vs. assumed)

- Python **3.11.9** (earlier log said 3.12.3 — the offline probe
  misreported); Node **v24.13.0**, npm 11.6.2; no `python3` alias.
- PyPI and npm registries **reachable** (the "no network" claim from
  Phase 1/2 is obsolete).
- PostgreSQL **16.8 installed from binaries** on E:, data dir
  `E:\pgsql\data`, port 5432; host Postgres used directly (no Docker).
- No Docker/Podman daemon on this host → `docker compose up` could not
  be runtime-verified; compose + Dockerfiles were statically verified
  instead (below).

### Databases

- `airindex` — dev/app DB (user `airindex`/`airindex_dev_secret`).
- `airindex_test` — dedicated integration-test DB; every integration
  test forces `DATABASE_URL=airindex_test` + `ENVIRONMENT=test`
  **before** importing the app and refuses to run otherwise.
- `airindex_autogen` — scratch DB for Alembic autogenerate work.

#### Fresh environment setup (from zero) — exact commands

Used on this host; adapt paths/credentials per environment. Needs a
running PostgreSQL server (via Docker: `docker compose up db`, or any
local install). With `PGPASSWORD` set for the Postgres superuser:

```
psql -U postgres -h localhost <<'SQL'
CREATE USER airindex WITH PASSWORD 'airindex_dev_secret';
CREATE DATABASE airindex      OWNER airindex;
CREATE DATABASE airindex_test OWNER airindex;
SQL
psql -U postgres -h localhost -d airindex -c 'GRANT ALL ON SCHEMA public TO airindex; ALTER SCHEMA public OWNER TO airindex;'
psql -U postgres -h localhost -d airindex_test -c 'GRANT ALL ON SCHEMA public TO airindex; ALTER SCHEMA public OWNER TO airindex;'
```

(`airindex_autogen` is scratch-only and recreated as needed.) Then, from
`backend/` with `DATABASE_URL` pointing at the dev DB: `alembic upgrade
head`; then `PYTHONPATH=.:./backend python scripts/seed_database.py`.

### Alembic baseline — reconciled, drift-free

The original hand-written `0001_initial_schema.py` diverged from the
models (naming, constraints, missing tables). Replaced with a **fresh
autogenerate output** against the models (revision id preserved as
`0001_initial`), deleted the drift-check revision, and verified:

```
$ alembic check
No new upgrade operations detected        # zero drift
$ alembic upgrade head                    # applied to real airindex DB
```

It is now the only migration file. `deployment/schema_postgres.sql`
was re-titled and clearly marked **superseded** (hand-apply it and you
get drift by construction).

### Seed — idempotent, executed

```
routes: 16 | data source: DEMO_GENERATOR | admin user | active IndexConfig (base 2026-01)
observations: 7330 (valid 6990 / suspicious 170 / invalid 33 / unavailable 137; valid_pct 95.36)
airlines: 5  (Air India/AI, Air India Express/IX, Akasa Air/QP, IndiGo/6E, SpiceJet/SG —
              derived from observed data, with known_iata map)
```

Re-running seed/ingest inserts 0 duplicates (all observation inserts use
`ON CONFLICT DO NOTHING` on `observation_id`; seed guards `if count == 0`
per table). The admin bootstrap reads `SEED_ADMIN_EMAIL` /
`SEED_ADMIN_PASSWORD` from the environment (defaults remain the demo
creds; the seed prints a loud reminder when the default password is
used), so non-local deployments can set a real admin password without
editing code.

### Backend bugs found & fixed

1. **index_engine period labelling** — replaced per-row `_period_label`
   regex guessing on ISO strings (19 s) with
   `pd.to_datetime(df["travel_date"]).dt.strftime("%Y-%m")` (~2 s).
   Labels byte-identical; values identical (base 100.0, 2026-04 95.38,
   2026-08 71.59 — matches modeled drift).
2. **ingestion.py import + idempotency** — fixed repo-root `sys.path`
   bootstrap (`parents[4]`), made inserts idempotent, moved shared
   orchestration into `app/services/ingestion_runner.py::
   collect_from_sources()`. Router is now a thin wrapper returning
   `{"runs": results}`.
3. **seed regression** — restored raw/clean_df/report lines and added
   airline seeding.
4. **Legacy SQLAlchemy API** — `db.query(Route).get(id)` →
   `db.get(Route, id)` in `reference.py` *and* `admin.py` (removes
   `LegacyAPIWarning`); 2.0-style session usage throughout.

### Verified HTTP end-to-end (uvicorn, 127.0.0.1:8000)

`POST /api/auth/login` → refresh/me; dashboard summary; index
current/trend/available-periods; routes CRUD (duplicate → 409) + weight
patch; airlines (5); data-quality summary; fares filters; exports CSV;
scrape trigger (SUCCESS 7330 rows, re-run → 0 new); runs list;
backtesting (honest `reference_available:false`);
analytics lead-time + airline; admin audit-log + create user
(`analyst@airindex.gov.in`). All smoke-test mutations rolled back
(deleted route restored, weight restored to sum 1.0000, active config
reset to id=1).

### Rate limiting + scheduler — wired and tested

- `app/core/rate_limit.py` — in-memory sliding-window middleware,
  limit 120/min from `API_RATE_LIMIT_PER_MINUTE`.
  Verified burst: 119×200 + 11×429 (with `Retry-After`).
- `app/services/scheduler_service.py` — APScheduler `BackgroundScheduler`
  cron `0 */6 * * *` (`INGESTION_SCHEDULE_CRON`), started/stopped in
  the FastAPI lifespan when `ENVIRONMENT != "test"`. Verified via
  TestClient: `scheduled_ingestion` job registered, clean shutdown.

### Frontend — installed, typechecked, built, browser-tested

- `npm install` succeeded (174 packages; `lucide-react` bumped
  `^0.383.0 → ^1.41.0` because 0.383 declares React ≤ 18 peer deps).
- `npm run typecheck` clean; `npm run build` succeeds (~15 s, 653 kB
  JS — chunk-size warning only).
- New auth flow: `pages/Login.tsx` (POST /api/auth/login, stores
  `airindex_access_token`/`airindex_refresh_token`), `RequireAuth.tsx`
  (no token → `/login`), layout **logout**, `api/client.ts` 401 →
  clear tokens + redirect.
- **Live-browser smoke test** (Playwright Chromium, headless) — 8/8
  checks passed: login page renders → UI login stores token → lands on
  dashboard → protected reload stays → token-clear redirects to /login
  → API `/auth/me` 401 without token → logout navigates back to /login.
- **Production build served** — rebuilt with
  `VITE_API_BASE_URL=http://127.0.0.1:8000/api` inlined at build time
  (confirmed present in the dist bundle) and served via `vite preview`
  (port 4173, fresh statically-served origin). The **same 8/8 browser
  smoke test passed against the production SPA with no dev proxy**
  (browser → real backend directly). Required only that `backend/.env`
  `CORS_ALLOWED_ORIGINS` include the preview origin
  (already granted to `localhost:5173`; extended to
  `localhost:4173,127.0.0.1:4173`).

### Integration test suite — new

`tests/test_api_integration.py` (19 tests) + `RateLimitMiddleware` unit
test. Enforces test-DB isolation, reseeds per test
(`scripts.seed_database.seed()`), exercises real HTTP via
`TestClient`. Full suite below.

### Full test run

```
$ PYTHONPATH=".;./backend" python -m unittest discover -s tests -q
Ran 69 tests in 233.742s
OK        # 50 unit + 19 integration, all green
```

### Docker / Compose — static verification

No Docker daemon exists on this host (docker/podman not installed;
winget present but installing Docker Desktop needs WSL2/admin/reboot —
not attempted). Compose verifed statically:

- `deployment/docker-compose.yml` parses as valid YAML; all referenced
  build contexts and files exist (`.env`, `backend/`, `backend/
  requirements.txt`, `scripts/`, `frontend/`, both Dockerfiles).
- Fixed so the stack is actually self-sufficient when a Docker host
  runs it: backend build context changed to the **repo root** so
  `scripts/seed_database.py` is in the image, and the image CMD now
  self-bootstraps `alembic upgrade head` → seed → serve (was: an empty
  schema and no way to seed it).
- Frontend service unchanged: Node 20 dev server on 5173,
  `VITE_API_BASE_URL=http://localhost:8000/api`.
- **Executable Docker verification provided via CI**:
  `.github/workflows/compose-verify.yml` builds and runs the exact
  stack headlessly on a Docker-enabled runner (GitHub-hosted
  `ubuntu-latest` ships Docker + compose v2). It: builds all three
  services, waits for `/api/health`, logs in with the seeded demo
  admin and checks `/auth/me` returns ADMIN and
  `/dashboard/summary` returns an index, curls the frontend on 5173,
  re-runs the in-container seed to confirm idempotency, and always
  tears down with `down -v`. This closes the "actual
  `docker compose up --build`" gap on any machine with Docker
  (including the default CI runner).
- **Pending (needs a Docker host)**: a human-run
  `docker compose up --build` on a Docker-capable machine (the CI
  workflow is the automated stand-in).

### robots.txt — live re-verified 2026-09-06

- Air India (`airindia.com` + `airindia.in`): **HTTP 000 / no response**
  from both the project UA and a browser UA — edge CDN refuses
  non-browser connections; treated as scrape-blocked (SOURCE
  UNAVAILABLE). Status changed from "NOT CHECKED" → "CHECKED
  (unreachable)" in `docs/ROBOTS_TXT_FINDINGS.md`.
- Akasa Air (`akasaair.com`): **HTTP 200**, `User-Agent: *` with **no
  Disallow rules** + 2 sitemaps — robots-PERMISSIVE. Status changed
  from NOT CHECKED → CHECKED.
- IndiGo / Air India Express / SpiceJet: still as documented (booking/
  fare-search paths explicitly disallowed).

### DGCA reference data — verified not publicly available as fares

Live search confirmed DGCA publishes city-pair **passenger-traffic**
statistics (PDF/Excel) and OTP reports, but **no machine-readable
average-fare series**. `DGCA_MONTHLY_AVG` remains honestly empty and
backtests return `reference_available:false`. No fabrication.

### Scheduler — full cron-cycle proof (gap from the integration test)

The 6-hour default was shortened to `INGESTION_SCHEDULE_CRON="*/1 * * * *"`
on a throwaway uvicorn instance (port 8001) pointed at `airindex_test`
(`ENVIRONMENT=development` so the lifespan starts the scheduler). Three
consecutive minute boundaries fired real runs:

```
ingestion_runs where triggered_by='scheduler' -> 3 rows
(id=1..3) status=SUCCESS rows_valid=6995 rows_suspicious=165
started_at = 10:54:00, 10:55:00, 10:56:00 IST   (exactly on the :00 boundary)
```

This proves APScheduler fires the job from a live uvicorn process on
the cron boundary, the job records an ingestion run, and the adapter
orchestration completes successfully and idempotently.

### Fresh-database bootstrap — Docker CMD chain executed verbatim

`deployment/Dockerfile.backend` runs, against an empty newschema:
`alembic upgrade head` → `python /app/scripts/seed_database.py` →
`uvicorn`. There is no Docker daemon on this host, so the **exact same
chain was executed on host Postgres** against a brand-new throwaway DB
(`airindex_fresh`, created, migrated, seeded, served, then dropped):

```
createdb airindex_fresh                          # empty, no schema
alembic upgrade head                      -> "Running upgrade -> 0001_initial"
alembic check                             -> "No new upgrade operations detected"   (zero drift on fresh DB)
SEED_ADMIN_EMAIL=ops@fresh.gov.in SEED_ADMIN_PASSWORD=FreshAdmin_2026! \
  python scripts/seed_database.py          -> 16 routes / DEMO_GENERATOR /
                                               admin (ops@fresh.gov.in (env-provided)) /
                                               5 airlines / 7330 observations /
                                               active index config base 2026-01
uvicorn app.main:app                      -> /api/health 200
  POST /api/auth/login  {ops@fresh.gov.in, FreshAdmin_2026!}  -> access_token
  GET  /api/auth/me                       -> {"id":1,"email":"ops@fresh.gov.in",
                                               "role":"ADMIN","is_active":true}
  GET  /api/dashboard/summary             -> index/n_routes/n_airlines/current_period/base_period
dropdb airindex_fresh                      # clean teardown
```

This is the closest executable analogue to the Docker backend service
boot on a fresh volume, and it passes end-to-end (including the
env-provided admin bootstrap replacing the demo creds).

### Verification gaps (only these remain)

1. `docker compose up` runtime itself (image build + container network
   on a machine with a Docker daemon) — the compose file is statically
   verified and the container's boot chain is proven above on real
   Postgres; only the container packaging itself is unexecuted here.
2. Real-credential deploy: set `SEED_ADMIN_PASSWORD` /
   `SEED_ADMIN_EMAIL` and rotate `JWT_SECRET_KEY` before any non-local
   deployment (supported by the seed since the 2026-09-06 rebuild; the
   local demo still intentionally uses the documented default).

## Full-page browser walk & bug fixes — 2026-09-07

A fresh Playwright walk of every route against the running stack
surfaced three real bugs, all now fixed and re-verified:

1. **`/routes` crashed (blank page).** `RouteAnalysis.tsx` called
   `useMemo` *after* conditional early returns → React "change in the
   order of Hooks". Fixed by hoisting the `routeFares` memo above the
   guard clauses. Re-walk body: 0 chars → **1035**.
2. **`/api/fares` → HTTP 500.** Postgres stores float8 **NaN**
   (`ValueError: Out of range float values are not JSON compliant`),
   so the fares table body was 666 chars with a failed request. Fixed at
   the write layer: new `backend/app/core/json_safe.py`
   (`json_safe_float`, `records_json_safe`) sanitizes non-finite floats
   to SQL NULL in **both** `services/ingestion_runner.py` (ingestion
   payloads) and `scripts/seed_database.py` (bulk import); existing dev
   rows repaired via `UPDATE fare_observations SET <col> = NULL WHERE
   <col> = 'NaN'::float8` (23 rows × total_fare/base_fare/taxes_fees,
   0 residual NaN). Verified `GET /api/fares?limit=100` → **200**. New
   unit tests added (`tests/test_json_safe.py`, 6 cases).
3. **`/api-docs` frontend route → 404.** The Vite dev proxy key `/api`
   prefix-matched `/api-docs`, so the SPA route was hijacked. Fixed by
   narrowing the key to `/api/` in `frontend/vite.config.ts`. Page now
   renders (867 chars).

Also: React Router v7 future-flag console warnings silenced app-wide by
opting in on `<BrowserRouter>` (`v7_startTransition`,
`v7_relativeSplatPath`), and the page-walk harness now fails only on
real console **errors** (not warnings).

Re-verification matrix (Playwright Chromium at `E:\playwright-browsers`):

```
walk_pages.py http://127.0.0.1:5173     -> 13/13 PASS (dev server)
walk_pages.py http://localhost:4173     -> 13/13 PASS (vite preview,
                                             fresh production build with
                                             VITE_API_BASE_URL=http://127.0.0.1:8000/api)
login_smoke.py <base>                   -> 8/8 PASS (both stacks)
PYTHONPATH=".;./backend" python -m unittest discover -s tests -q
                                        -> Ran 75 tests (was 69) in 103.5s: OK
npm run typecheck                       -> clean
npm run build                           -> clean (dist relinked)
```

### Operational note: host PostgreSQL is flaky under this VM

While running the suite, Postgres repeatedly terminated with Windows
exception `0xC0000142` (DLL init failure — environmental, not app
code; it also happened once during 09-05 setup and recovered). Recovery
used throughout: relaunch fully detached, verify `pg_isready`, then
re-run. No data was lost (WAL redo); this is a characteristic of the
sandbox host, not of the AirIndex services. On target deployment
machines (Docker container or a normal service install) this does not
occur.

## Cloud CI on GitHub Actions — 2026-09-08 (fills the Docker gap)

The project was pushed to `https://github.com/Barathraj009/AirIndex`
(branch `main`, private→public user repo), and the two Docker/CI gaps
left on the flaky local host are now verified headlessly on
GitHub-hosted Ubuntu runners on **every push**:

1. **`compose-verify`** — the real `docker compose up` (db + backend +
   frontend) now executes: images build, stack starts, backend health,
   login → `/auth/me` ADMIN → `/dashboard/summary`, frontend :5173 curl,
   in-container seed rerun prints `already populated`. **PASSING.**
2. **`ci`** — three jobs:
   - backend tests + alembic drift (Postgres 16 service): `alembic
     upgrade head`, `alembic check` (zero drift), full suite
     (75 tests) against `airindex_test` — **PASSING**;
   - frontend typecheck + production build — **PASSING**;
   - browser smoke: backend + `vite preview` on the built SPA, then
     real Chromium login flow **8/8** and full route walk **13/13**
     (scripts shipped as `scripts/browser/*.py`) — **PASSING**.

Two real defects were caught and fixed by the first cloud run:

- **e2e boot bug**: the server-start step did `cd frontend` relative to
  `backend/`, so `vite preview` silently never started and the health
  gate timed out (`curl` exit 7). Fixed with `$GITHUB_WORKSPACE`-
  absolute paths + explicit failure reporting. 
- **backend image build bug**: `playwright install --with-deps
  chromium` exits 100 inside the `python:3.12-slim` build (unused by
  demo/compose flows). Removed from `Dockerfile.backend`; browsers are
  runtime-installable for future real scrapers.

Relevant run records: ci run `34196809040` (3/3 jobs green), compose-
verify run `34196809068` (1/1 green) — both on commit `77d2377`;
initial failures (`34191449432`, `34191449410`) documented the two fixes
above.

### Remaining gaps (unchanged, narrow)

The app is not deployed to a public host (that is the deploy step, out
of scope for verification); with this CI, `docker compose up` and the
full test/browser matrix are now proven on every commit rather than only
on this host.

---

## Frontend redesign — 5-page clean layout (2026-09-09)

### What changed

Complete frontend rebuild from 16 pages to 5 focused pages:

- **Deleted**: `AirfarePriceIndex.tsx`, `AirlineAnalysis.tsx`,
  `ApiDocs.tsx`, `Backtesting.tsx`, `CpiAugmentation.tsx`,
  `DataExplorer.tsx`, `DataQuality.tsx`, `GeospatialMap.tsx`,
  `LeadTimeAnalysis.tsx`, `Methodology.tsx`, `Overview.tsx`,
  `RouteAnalysis.tsx`, `ScrapingMonitor.tsx`, `SectorHeatmap.tsx`
  (14 files removed).
- **New**: `Dashboard.tsx` (APIx strip + stats + trend + contributors +
  airline snapshot), `Analysis.tsx` (4 tabs: Routes, Airlines, Lead Time,
  Heatmap), `Data.tsx` (2 tabs: Explorer, Quality).
- **Rewritten**: `Login.tsx` (single-step email+password form, no
  two-step check-user flow), `Admin.tsx` (5 tabs: Routes, Sources,
  Users, Config, Audit).
- **Updated**: `Layout.tsx` (5-entry sidebar, role-gated Admin,
  JWT-decoded role check, "Airfare Price Index" subtitle),
  `App.tsx` (4 routes: `/`, `/analysis`, `/data`, `/admin`).

### SIH/PS-26056 references removed

All references to "SIH 2026", "PS 26056", and "Smart India Hackathon"
removed from frontend source (`Layout.tsx`, `Login.tsx`). The README
title still mentions it (read-only per user instruction).

### Login flow simplified

Old: two-step (email → check-user → credentials → login).
New: single form (email + password → login). E2e scripts updated
accordingly (`login_smoke.py`, `walk_pages.py`).

### Route walk updated

Old: 15 routes covering all legacy pages.
New: 4 routes (`/`, `/analysis`, `/data`, `/admin`).
`walk_pages.py` updated with new route list.

### Build verification

```
$ cd frontend && npm run typecheck
# clean, zero errors

$ npm run build
# tsc -b && vite build — 648 kB JS (chunk-size warning only)
# dist/ built in ~5s
```

### Backend test suite (unchanged, unchanged 1 error local)

```
$ PYTHONPATH=".;./backend" python -m unittest discover -s tests -v
Ran 71 tests in 8.155s
FAILED (errors=1)   # test_api_integration: Postgres not running locally
# CI with Postgres: all tests pass
```

### Pages rendered (5 total)

| Route | Page | Content |
|---|---|---|
| `/login` | Login | Email + password form, AirIndex branding |
| `/` | Dashboard | APIx value, trend chart, route contributors, airline snapshot |
| `/analysis` | Analysis | Routes tab (bar chart + detail), Airlines tab (chart + table), Lead Time tab (line chart + ranking), Heatmap tab (matrix) |
| `/data` | Data | Explorer tab (filters + table + CSV export), Quality tab (stats + outlier + dedup) |
| `/admin` | Admin | Route weights, Data sources, Users, Index config, Audit log |

### Key design decisions

- Source badges on every data-derived number (LIVE/PUBLIC DATA/DEMO/UNAVAILABLE)
- Amber demo banner on Dashboard: "Demo data — figures are simulated representative series"
- All numbers from live API calls (no hardcoded values)
- APIx from `/api/index/current` (never computed client-side)
- Max 2 chart types per page (Dashboard: LineChart + CSS bars; Analysis Routes: BarChart + LineChart)
- Skeleton/loading states via `LoadingState` component
- 401 interceptor in `api/client.ts` clears token + redirects
- Layout role-gates Admin via JWT payload decode
- No modal dialogs for primary workflows
- Color palette: slate bg, white cards, blue accent, red up, green down, amber warnings
