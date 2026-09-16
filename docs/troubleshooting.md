# Troubleshooting

Common symptoms and fixes for the two-source product (MoSPI CPI +
Google Flights feed).

## Google Flights feed reports SOURCE UNAVAILABLE

- **Missing `RAPIDAPI_KEY`.** Without the key the `GOOGLE_FLIGHTS_API`
  adapter stays inert and raises `SourceUnavailableError`. Set
  `RAPIDAPI_KEY` in `.env` (RapidAPI, provider `google-flights8`,
  host `google-flights8.p.rapidapi.com`) and restart the backend.
- **Invalid/expired key, or quota exhausted.** The Basic $0 plan is
  rate-limited. Check the source's `last_failure_reason` on the
  `data_sources` row and the `ingestion_runs` rows; a `401/403` means
  the key, an HTTP 429 means quota.
- **No network egress.** The backend host must be able to reach
  `google-flights8.p.rapidapi.com` over HTTPS.

## MoSPI CPI refresh failures

- **MoSPI API unreachable / TLS issue.** `api.mospi.gov.in` uses legacy
  TLS renegotiation; `ingestion/adapters/mospi_cpi.py` handles this via
  `SSL_OP_LEGACY_SERVER_CONNECT`. If it still fails, it's usually a
  transient outage or egress restriction.
- **No new months.** MoSPI publishes around the 12th of each month; the
  table keeps the last known series, so a refresh that returns nothing
  new is expected mid-month. `populate_cpi.py` inserts with
  `ON CONFLICT DO NOTHING` on `period`, so re-runs are idempotent.
- **Diagnose a run.** `GET /api/ingestion/runs` (with auth) shows the
  last run per source, its status, and `error_message` for the failure.

## The index changed after a refresh — is that expected?

Yes. The combined CPI airfare series anchors on the official MoSPI
index and is blended with live Google Flights fares, so a month where
MoSPI republishes or where live fares shift will move APIx. Per-run
`calculation_breakdown` in `index_runs` explains exactly which routes
and windows drove the change.

## SQLite vs Postgres

- The app is designed for **PostgreSQL 16**. Local unit-test runs of
  individual modules can use sqlite for offline schema checks
  (`tests/sqlite_schema.py`), but the integration suite requires
  Postgres: `tests/test_api_integration.py` forces
  `DATABASE_URL=airindex_test` and fails at `setUpClass` without a
  running Postgres server — not a regression.
- **Float/NaN:** Postgres stores `float8` NaN which the JSON encoder
  rejects. The write layer sanitizes non-finite floats to NULL
  (`backend/app/core/json_safe.py`); sqlite does not reproduce this
  surface, so verify against Postgres.
- **`alembic check` reports drift.** Run `alembic upgrade head` first;
  the baseline plus `0008` must be applied to match the models. On a
  fresh DB, `alembic check` returns "No new upgrade operations detected".

## Salt / credentials

- `RAPIDAPI_KEY` and the JWT secret are read from the environment; never
  commit a real `.env`. Missing `JWT_SECRET_KEY` or the placeholder value
  blocks the app in `ENVIRONMENT=production`.
- Reset the seeded admin password (default `change-me-immediately`) via
  `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` before any non-local deploy;
  production refuses the default.