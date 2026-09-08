# AirIndex India — SIH 2026, PS 26056

[![ci](https://img.shields.io/github/actions/workflow/status/Barathraj009/AirIndex/ci.yml?branch=main&label=ci)](https://github.com/Barathraj009/AirIndex/actions/workflows/ci.yml)
[![compose-verify](https://img.shields.io/github/actions/workflow/status/Barathraj009/AirIndex/compose-verify.yml?branch=main&label=compose-verify)](https://github.com/Barathraj009/AirIndex/actions/workflows/compose-verify.yml)

Real-time Airfare Price Index for India, built from automated fare
collection across airline/OTA sources, for augmentation of the CPI.

## Status — fully executed, verified locally (2026-09-06) and in cloud CI (2026-09-08)

Every component **runs and has been executed end-to-end on a real
machine**: Python 3.11 + PostgreSQL 16 + FastAPI/uvicorn backend,
React/Vite/TypeScript frontend, Alembic migrations, JWT/RBAC auth, rate
limiting, scheduled ingestion, and a live-browser login flow.

Since 2026-09-08 the project also lives on GitHub
(`Barathraj009/AirIndex`, branch `main`) and **every verification step
runs automatically in cloud CI on every push**, including the one thing
a Docker-less dev host could not do. GitHub-hosted runners (Ubuntu,
real Docker) run:

- **`compose-verify`** — builds both images and `docker compose up`s the
  full stack (db + backend + frontend), waits for health, smoke-tests
  login → `/auth/me` → `/dashboard/summary`, curls the frontend, checks
  seed idempotency in-container. **Passing.**
- **`ci`** — backend: `alembic upgrade head` + zero-drift `alembic
  check` + the full 75-test suite against Postgres 16; frontend:
  `npm ci` + `npm run typecheck` + production build; end-to-end:
  real-Chromium login flow (8 checks) + full 13-route page walk against
  the production build + live backend. **Passing.**
See `docs/VERIFICATION_LOG.md` for the full per-item record.

## What's built and verified

- **Index methodology** (`backend/app/services/index_engine.py`) — APIx
  v1.0.0, a configuration-driven modified-Laspeyres route-weighted
  index, with booking-window weights, route/airline contribution
  breakdown, missing-route renormalization, and a full
  calculation-breakdown trace. Vectorized period labelling (2026-09
  rebuild): 3-period trend computes in ~2 s vs ~19 s before, byte-identical output.
- **Data pipeline** (`backend/app/services/data_processing.py`) — IQR +
  MAD outlier detection, structural validation, data-quality status
  classification (VALID / SUSPICIOUS / INVALID / UNAVAILABLE).
- **Backtesting** (`backend/app/services/backtesting.py`) — MAE/RMSE/
  MAPE/correlation metrics; honestly returns `reference_available:false`
  rather than fabricating comparisons when no reference data exists.
- **Auth/RBAC** (`backend/app/core/security.py`) — JWT (PyJWT) +
  PBKDF2-SHA256 password hashing, ADMIN/ANALYST/VIEWER roles,
  access + refresh tokens.
- **Database** — PostgreSQL 16.8 on host port 5432. Alembic baseline
  (`backend/alembic/versions/0001_initial_schema.py`) was regenerated
  from the SQLAlchemy models and verified **drift-free**
  (`alembic check` = no new upgrade operations). Applied to the real DB
  and idempotently seeded.
- **API** — FastAPI routers for auth, dashboard, index, routes/airlines,
  fares/data-quality, ingestion (scrape trigger + run monitor),
  backtesting, analytics, exports, admin/audit. In-memory rate limiter
  (120 req/min, verified 429 + `Retry-After`), APScheduler cron job
  (every 6 h, disabled under `ENVIRONMENT=test`), CORS, global error
  handler, `/api/health`.
- **MoSPI CPI Augmentation Simulator** (`backend/app/services/cpi_engine.py`,
  `frontend/src/pages/CpiAugmentation.tsx`) — Models real-time integration
  of APIx into official Consumer Price Index (Base 2012=100) Transport group
  (~8.59% weight) and airfare subcomponent (~0.20% weight), computing headline
  inflation delta (bps), volatility capture, and ~45 days reporting lag reduction.
- **DGCA Traffic Calibration & Benchmarks** (`backend/app/services/dgca_service.py`) —
  Route basket weights calibrated with official DGCA annual domestic city-pair
  passenger traffic volume. 1-click admin auto-calibration and benchmark
  reference datasets for backtesting.
- **Geospatial Flight Corridor Map** (`frontend/src/pages/GeospatialMap.tsx`) —
  Interactive SVG map of India with airport hubs and animated flight corridors
  color-coded by fare inflation rate, with live Route Inspection HUD.
- **Surge Anomaly Detection & Forecasting** (`backend/app/services/anomaly_detector.py`,
  `backend/app/services/forecaster.py`) — Route price gouging / surge spike alerts
  and 1–3 month time-series forward index projections with 80% & 95% confidence bands.
- **Full Admin Console** (`frontend/src/pages/Admin.tsx`) — 5 dedicated tabs:
  Route Weights (with DGCA auto-calibration), Data Sources controller, User
  Management (roles & status toggling), Index Configuration, and Audit Log.
- **Official Monthly Statistical Bulletin** (`backend/app/api/routers/bulletin.py`) —
  Automated MoSPI/DGCA executive summary export (`/api/exports/monthly-bulletin`).
- **Frontend** — React + TypeScript + Vite + Tailwind + Recharts. 15 comprehensive
  pages with full navigation, typed API client, Change Password modal, and auth guards.
- **Seed** (`scripts/seed_database.py`) — idempotent: 16 routes, 7330 fare observations,
  multi-role accounts (ADMIN, ANALYST, VIEWER), all data sources, DGCA benchmark data.
- **Report Generation** (`backend/app/services/reports.py`) — PDF executive reports
  (reportlab) and Excel workbooks (openpyxl) from IndexResult. Available via
  `GET /api/reports/export?formats=pdf,excel` with auth.
- **Surge Alert Notifications** (`backend/app/services/alerts.py`) — Configurable
  threshold-based alerting with SMTP email and webhook notification channels.
  `GET /api/alerts/check` and `POST /api/alerts/check-and-notify` endpoints.
- **Deployment Analysis** (`DEPLOYMENT_ANALYSIS.md`) — Free platform comparison
  (Render recommended) with migration steps and env var mapping.


## Test suite — 75 tests, all passing

```
PYTHONPATH=".;./backend"  python -m unittest discover -s tests      # 75 tests: OK
PYTHONPATH=".;./backend"  python -m unittest tests.test_api_integration -v
```

Windows/PowerShell:

```powershell
$env:PYTHONPATH=".;./backend"; .venv\Scripts\python.exe -m unittest discover -s tests -q
```

50 unit tests cover the analytical core, security, DB schema, rate
limiter, and scheduler wiring. 19 integration tests hit the **real
HTTP API** (`FastAPI.testclient`) against a dedicated
`airindex_test` database — every test forces
`DATABASE_URL=airindex_test` + `ENVIRONMENT=test` before app imports and
refuses to run against any other DB, then wipes + reseeds per test. The
suite does not touch the dev database.

## Running it locally (verified on Windows/PowerShell)

Prereqs: Python 3.11+, a running PostgreSQL 16 server, Node 20+.

```powershell
# 0. install
python -m venv .venv; .venv\Scripts\pip.exe install -r backend\requirements.txt
npm --prefix frontend install

# 1. env
copy .env.example .env        # then fill in DATABASE_URL, JWT secret, etc.

# 2. create db + user (once) per VERIFICATION_LOG, then migrate + seed
cd backend; ..\.venv\Scripts\alembic.exe upgrade head; ..\.venv\Scripts\python.exe ..\scripts\seed_database.py

# 3. backend API
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. frontend
cd ..\frontend; npm run dev -- --host 127.0.0.1
# open http://127.0.0.1:5173/  ->  login  ->  dashboard
```

The Vite dev server proxies `/api` to the backend on 127.0.0.1:8000.
To also exercise the **production build** (statically served, no proxy),
point the build at the backend once and serve it:

```powershell
cd frontend; $env:VITE_API_BASE_URL="http://127.0.0.1:8000/api"; npm run build
npm run preview -- --port 4173     # then open http://localhost:4173/ (backend CORS covers this origin)
```

## Docker (statically verified; automated runtime verification included)

```bash
cp .env.example .env
docker compose -f deployment/docker-compose.yml up --build
```

`.github/workflows/compose-verify.yml` runs this exact stack headlessly
on any Docker-enabled CI runner (builds all services, waits for health,
logs in as the seeded admin, smoke-tests API + frontend, confirms seed
idempotency, always tears down) — the executable stand-in for a Docker
host on machines that lack one.

- `db` — `postgres:16-alpine`, named volume, healthcheck-gated.
- `backend` — built from repo root; runs `alembic upgrade head` then
  the idempotent seed, then serves on 0.0.0.0:8000 (single mount of
  `backend/`; `scripts/` baked into the image). `DATABASE_URL` is
  overridden to point at the `db` service.
- `frontend` — Node 20, `npm run dev -- --host 0.0.0.0` on 5173 with
  `VITE_API_BASE_URL=http://localhost:8000/api` (browser reaches the
  published backend port directly, so no in-container proxy is needed).

## Auth — demo credentials

| Role | Email | Password |
|---|---|---|
| ADMIN | `admin@airindex.gov.in` | `change-me-immediately` |

The JWT secret and admin password are local-only dev values. **Rotate
the JWT secret in `.env` and change the admin password before any
non-local deployment** (seed prints a loud reminder on every run).
Deployments can set a real admin upfront via `SEED_ADMIN_EMAIL` /
`SEED_ADMIN_PASSWORD` env vars (see `.env.example`) instead of using
the demo creds. A second user (`analyst@airindex.gov.in`, ADMIN-created)
is also in the audit log.

## Data source labeling — honesty constraints

Every observation and index calculation carries a `source_type`:
`LIVE_SCRAPE`, `PUBLIC_DATASET`, or `DEMO_SIMULATED`. When a source
can't be reached the adapter raises `SourceUnavailableError` and the UI/
API shows **SOURCE UNAVAILABLE** rather than silently dropping or
fabricating data. Simulated data is never presented as live. Auto-ingest
adapters are robots.txt-driven, rate-limited, and never bypass CAPTCHA
or login walls.

### robots.txt reality (checked live, see `docs/ROBOTS_TXT_FINDINGS.md`)

IndiGo, Air India Express, and SpiceJet **explicitly disallow** the
booking/fare-search paths a scraper would need. Akasa Air is
robots-permissive (no Disallow rules). Air India's edge CDN refuses even
the robots.txt fetch (HTTP 000). The system therefore runs the robust
`DemoAdapter` + `SOURCE_UNAVAILABLE` path; real airline fare collection
should go through official OTA partner/affiliate APIs or public
datasets, not airline-site scraping.

### DGCA reference data for backtesting

DGCA publishes city-pair passenger *traffic* statistics and OTP
reports, but **no machine-readable average-fare series**. The
`DGCA_MONTHLY_AVG` reference source is therefore honestly empty and the
backtester returns `reference_available:false` until a real dataset is
made available — nothing is fabricated to paper over it.

## Methodology summary (APIx v1.0.0)

Modified Laspeyres route-weighted index. For each route, the
representative fare per period is the median total fare across
configured booking windows (booking-window-weighted). The index is the
weighted mean of route-level price relatives (current/base), ×100. Full
math and rationale: `backend/app/services/index_engine.py` docstring and
`docs/METHODOLOGY.md`.

## Key docs

- `docs/VERIFICATION_LOG.md` — per-item build/verification record.
- `docs/METHODOLOGY.md` — index math, weights, real reference data point.
- `docs/ROBOTS_TXT_FINDINGS.md` — live robots.txt findings per airline.
- `deployment/` — `docker-compose.yml`, both Dockerfiles,
  `schema_postgres.sql` (superseded reference; use Alembic).

## Cloud CI

Workflows live in `.github/workflows/` and run on every push to `main`:
`ci.yml` (backend tests + Alembic drift, frontend typecheck/build, and a
Playwright browser e2e against the real stack) and `compose-verify.yml`
(the full `docker compose up` stack). Health: both **passing** on
`Barathraj009/AirIndex`.