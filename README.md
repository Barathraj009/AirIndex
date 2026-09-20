# AirIndex India

[![ci](https://img.shields.io/github/actions/workflow/status/Barathraj009/AirIndex/ci.yml?branch=main&label=ci)](https://github.com/Barathraj009/AirIndex/actions/workflows/ci.yml)
[![compose-verify](https://img.shields.io/github/actions/workflow/status/Barathraj009/AirIndex/compose-verify.yml?branch=main&label=compose-verify)](https://github.com/Barathraj009/AirIndex/actions/workflows/compose-verify.yml)

Real-time Airfare Price Index for India, backed by two real data
sources: the official MoSPI CPI airfare index (code 07.3.3.1) and a
licensed live Google Flights fare feed.

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
  check` + the full test suite against Postgres 16; frontend:
  `npm ci` + `npm run typecheck` + production build; end-to-end:
  real-Chromium login flow (8 checks) + full-route page walk against
  the production build + live backend. **Passing.**
See `docs/VERIFICATION_LOG.md` for the full per-item record.

## What's built and verified

- **Two real data sources** —
  - **MOSPI_CPI** (`ingestion/adapters/mospi_cpi.py`) — the official
    MoSPI CPI airfare index, code **07.3.3.1** ("Passenger transport by
    air, domestic"), base **2024=100**, published monthly by the
    Ministry of Statistics and Programme Implementation. Fetched live
    from `api.mospi.gov.in` and stored in `cpi_airfare_index`. This is
    the anchor series for the combined airfare index.
  - **GOOGLE_FLIGHTS_API** (`ingestion/adapters/gds_adapter.py`) — live
    Google Flights calendar fares via the licensed RapidAPI
    `google-flights8.p.rapidapi.com` feed (Basic $0 plan). One
    `price-graph/one-way` call per route returns the full ~91-day
    calendar, covering every booking window in a single request;
    near-horizon sparse responses trigger a short-horizon backfill.
    Prices arrive in USD and are converted to INR at `FX_RATE_USD_INR`.
    Observations flow through the same validation/index pipeline as the
    MoSPI series.
- **Index methodology** (`backend/app/services/index_engine.py`) — APIx
  v1.0.0, a configuration-driven modified-Laspeyres route-weighted
  index, with booking-window weights, route/airline contribution
  breakdown, missing-route renormalization, and a full
  calculation-breakdown trace. Vectorized period labelling (2026-09
  rebuild): 3-period trend computes in ~2 s vs ~19 s before, byte-identical output.
- **Data pipeline** (`backend/app/services/data_processing.py`) — IQR +
  MAD outlier detection, structural validation, data-quality status
  classification (VALID / SUSPICIOUS / INVALID / UNAVAILABLE).
- **Combined CPI airfare series** (`backend/app/services/cpi_engine.py`) —
  Merges the live fare feed into the official CPI airfare index,
  producing a single combined airfare series, headline inflation delta
  (bps), volatility capture, and reporting-lag analysis relative to the
  official monthly publication cycle.
- **Route basket** (`backend/app/services/route_basket.py`) — 16
  domestic city-pair routes covering the trunk and regional markets,
  with weights proportional to approximate all-India domestic
  passenger-traffic share. Admin-overridable via the routes table/API.
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
  fares/data-quality, ingestion (trigger + run monitor), cpi, backtesting,
  analytics, exports, admin/audit. In-memory rate limiter
  (120 req/min, verified 429 + `Retry-After`), APScheduler cron job
  (daily 06:00 UTC by default — see `INGESTION_SCHEDULE_CRON`, disabled
  under `ENVIRONMENT=test`), CORS, global error
  handler, `/api/health`.
- **3D Visualization** (`frontend/src/pages/Analysis.tsx`) — Index trend,
  YoY/MoM inflation, seasonality, forecast bands, route basket, and
  booking-window analysis with 2D, isometric, and WebGL 3D chart modes.
- **Surge Anomaly Detection & Forecasting** (`backend/app/services/anomaly_detector.py`,
  `backend/app/services/forecaster.py`) — Route price gouging / surge spike alerts
  and 1–3 month time-series forward index projections with 80% & 95% confidence bands.
- **Full Admin Console** (`frontend/src/pages/Admin.tsx`) — dedicated tabs:
  Route Weights, User Management (roles & status toggling), and Index Configuration.
- **Official Monthly Statistical Bulletin** (`backend/app/api/routers/bulletin.py`) —
  Automated MoSPI executive summary export (`/api/exports/monthly-bulletin`).
- **Frontend** — React + TypeScript + Vite + Tailwind + Recharts + ECharts GL.
  Core pages (Login, Dashboard, Analysis, Data, Admin) with full navigation,
  typed API client, Change Password modal, and auth guards.
- **Seed** (`scripts/seed_database.py`) — idempotent: the 16-route basket, the
  two real data-source rows, replayed real observations from both sources
  (`backend/app/services/replay_data.py`), multi-role accounts
  (ADMIN, ANALYST, VIEWER), and an active index configuration. No
  synthetic data is loaded.
- **Report Generation** (`backend/app/services/reports.py`) — PDF executive reports
  (reportlab) and Excel workbooks (openpyxl) from IndexResult. Available via
  `GET /api/reports/export?formats=pdf,excel` with auth.
- **Surge Alert Notifications** (`backend/app/services/alerts.py`) — Configurable
  threshold-based alerting with SMTP email and webhook notification channels.
  `GET /api/alerts/check` and `POST /api/alerts/check-and-notify` endpoints.


## Test suite — all passing

```
PYTHONPATH=".;./backend"  python -m unittest discover -s tests        # full suite: OK
PYTHONPATH=".;./backend"  python -m unittest tests.test_api_integration -v
```

Windows/PowerShell:

```powershell
$env:PYTHONPATH=".;./backend"; python -m unittest discover -s tests -q
```

Unit tests cover the analytical core, security, DB schema, rate
limiter, and scheduler wiring. Integration tests hit the **real HTTP
API** (`FastAPI.testclient`) against a dedicated `airindex_test`
database — every integration test forces
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
copy .env.example .env        # then fill in DATABASE_URL, JWT secret, and
                              # RAPIDAPI_KEY for the live Google Flights feed

# 2. create db + user (once), then migrate + seed
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

The MoSPI CPI airfare index is refreshed at server startup and on the
scheduled cadence (see `INGESTION_SCHEDULE_CRON`); the Google Flights
feed collects live fares per active route when `RAPIDAPI_KEY` is set.

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

## Deploy to Render

`render.yaml` defines the backend (docker web service), the static
frontend, and a free Postgres database. Blueprint deploy:
`New + → Blueprint → Barathraj009/AirIndex`. Set on **first deploy**:

| Var | Notes |
|---|---|
| `DATABASE_URL` | wired automatically from the `airindex-db` database |
| `JWT_SECRET_KEY` | auto-generated by Render |
| `RAPIDAPI_KEY` | the Google Flights feed key (leave unset = feed stays inert, everything else works) |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | admin bootstrap; `ENVIRONMENT=production` **refuses** the default password |
| `CORS_ALLOWED_ORIGINS` | the deployed frontend origin (`https://airindex-frontend.onrender.com` by default) |
| `INGESTION_SCHEDULE_CRON` | `0 6 * * *` daily (default) — ≈180 Google Flights requests/month on 6 routes |
| `FX_RATE_USD_INR` | 90.0 default; USD→INR reference rate for the feed |

The Blueprint also provisions **`airindex-otp`**, the Email-OTP auth
microservice (`otp-service/`), as its own free Node web service at
`https://airindex-otp.onrender.com` (health `/api/health`, CSRF-gated
`/api/auth/*`). Paste these secrets on its first deploy:

| Var (airindex-otp) | Notes |
|---|---|
| `OTP_SERVICE_JWT_SECRET` | MUST equal the backend's `OTP_SERVICE_JWT_SECRET` (the backend verifies this service's hand-off JWTs with it) |
| `GMAIL_USER` / `GMAIL_APP_PASSWORD` | Gmail App Password (not your real password) for OTP delivery |
| `OTP_HASH_SECRET` | long random string (`openssl rand -hex 32`) |

Status note: the OTP **service is deployed and sized** by this config, but
the React app's login page is not yet wired to it — `src/pages/Login.tsx`
is plain email/password today (the dev-only `/otp-auth/` proxy in
`vite.config.ts` is the only hook). Wiring the Email-OTP tab into the
login UI is a separate, pending frontend task.

The backend image waits for Postgres, `create_all`s the schema, runs
`bootstrap_reference.py` (route basket, the two data sources
`MOSPI_CPI` + `GOOGLE_FLIGHTS_API`, admin user, active index config —
**no** synthetic observations), then serves on :8000. The MoSPI CPI
table is populated at startup from `api.mospi.gov.in`. Set
`SEED_ADMIN_PASSWORD` to a strong value or the bootstrap aborts.

## Auth — default credentials

| Role | Email | Password |
|---|---|---|
| ADMIN | `admin@airindex.gov.in` | `change-me-immediately` |

The JWT secret and admin password are local-only dev values. **Rotate
the JWT secret in `.env` and change the admin password before any
non-local deployment** (seed prints a loud reminder on every run).
Deployments can set a real admin upfront via `SEED_ADMIN_EMAIL` /
`SEED_ADMIN_PASSWORD` env vars (see `.env.example`) instead of using
the defaults. A second user (`analyst@airindex.gov.in`, ADMIN-created)
is also in the audit log.

## Data source labeling — honesty constraints

Every observation and index calculation carries a `source_type`:
`LIVE_SCRAPE` (Google Flights live feed) or `PUBLIC_DATASET` (MoSPI).
When a source can't be reached the adapter raises `SourceUnavailableError`
and the UI/API shows **SOURCE UNAVAILABLE** rather than silently dropping
or fabricating data.

### Licensed live feed (Google Flights via RapidAPI)

The real-time fare source is a **licensed API feed** — the Google
Flights calendar prices endpoint (RapidAPI provider `google-flights8`,
host `google-flights8.p.rapidapi.com`). It sits on the same
`booking_window_weights`/route basket as the MoSPI series and appears
separately in the Dashboard as a **Live feed** pill. Enable it in any
environment with `RAPIDAPI_KEY` in `.env` (the feed source row is
seeded by `bootstrap_reference.py` in production and
`seed_database.py` for local dev). Daily cadence ≈ 180 RapidAPI
requests/month on 6 routes.

**One-time Render setup (production):** the backend service declares
`RAPIDAPI_KEY` with `sync: false` in `render.yaml`, so the key itself is
never stored in the repo. Paste the RapidAPI key in the Render dashboard
(backend service → Settings → Environment → `RAPIDAPI_KEY`, then a manual
deploy). Until that's done the deployed app still renders real data — the
bundled 2026-09-16 live capture replay + MoSPI index — but the scheduled
ingestion reports the Google Flights feed as SOURCE UNAVAILABLE.

### Official MoSPI index (07.3.3.1)

The MoSPI CPI airfare index (code **07.3.3.1**, base **2024=100**) is
the official domestic airfare price series for India, published
monthly by MoSPI. The platform fetches it live from
`api.mospi.gov.in` into `cpi_airfare_index` and anchors the combined
APIx series to it.

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
- `docs/data-schema.md` — live schema (CPI, fares, ingestion, index runs).
- `docs/source-status.md` — status of the two real data sources.
- `docs/troubleshooting.md` — common issues and fixes.
- `deployment/` — `docker-compose.yml`, both Dockerfiles,
  `schema_postgres.sql` (superseded reference; use Alembic).

## Cloud CI

Workflows live in `.github/workflows/` and run on every push to `main`:
`ci.yml` (backend tests + Alembic drift, frontend typecheck/build, and a
Playwright browser e2e against the real stack) and `compose-verify.yml`
(the full `docker compose up` stack). Health: both **passing** on
`Barathraj009/AirIndex`.