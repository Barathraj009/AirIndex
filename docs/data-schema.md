# Data Schema

The live schema is defined by the SQLAlchemy models in
`backend/app/models/` and applied via Alembic migrations (`0001` …
`0008`). Migration `0008` dropped the scraper/demo/WPI-ATF/DGCA tables;
the tables below are the ones the two-source product reads and writes.

## Core source tables

### `cpi_airfare_index` — official MoSPI CPI airfare series

Model: `app.models.cpi.CpiAirfareIndex` (migration `0004`).

| Column            | Type          | Notes                                              |
|-------------------|---------------|----------------------------------------------------|
| `period`          | `VARCHAR(7)`  | `YYYY-MM`, unique index.                           |
| `data_date`       | `DATE`        | Mid-month reference (15th of the month).           |
| `airfare_index`   | `FLOAT`       | CPI code 07.3.3.1, base 2024=100. **Not nullable.**|
| `transport_index` | `FLOAT`       | Transport division (code 07) — retained, legacy.   |
| `general_index`   | `FLOAT`       | All-items CPI (code 00) — retained, legacy.        |
| `inflation_yoy` / `inflation_mom` | `FLOAT` | Inflation metrics.                          |
| `source` / `source_url` / `cpi_code` / `base_year` | `VARCHAR` | Provenance (`MOSPI_CPI`, `07.3.3.1`, `2024=100`). |
| `fetched_at` / `created_at` | `TIMESTAMPTZ` | Audit timestamps.                         |

### `fare_observations` — live Google Flights feed

Model: `app.models.observations.FareObservation`. One row per
(route, airline, flight, travel_date, collection_timestamp) normalized
fare quote — the output of `data_processing.run_pipeline()` for the
`GOOGLE_FLIGHTS_API` source.

| Column                | Type              | Notes                                               |
|-----------------------|-------------------|-----------------------------------------------------|
| `observation_id`      | `VARCHAR(16)`     | Dedup hash, unique index.                           |
| `origin` / `destination` | `VARCHAR(3)`   | IATA airport codes, indexed.                        |
| `airline` / `flight_number` | `VARCHAR`   | Airline name (+ optional flight number).            |
| `travel_date`         | `DATE`            | Indexed.                                            |
| `collection_timestamp`| `TIMESTAMPTZ`     | When the fare was collected.                        |
| `booking_window_days` | `INT`             | T+n window, indexed.                                |
| `fare_class` / `base_fare` / `taxes_fees` / `total_fare` / `currency` | — | Fare components (currency defaults to INR). |
| `source` / `source_type` | `VARCHAR`      | `GOOGLE_FLIGHTS_API` / `LIVE_SCRAPE`.               |
| `data_quality_status` / `quality_flags` | `VARCHAR` | `VALID` / `SUSPICIOUS` / `INVALID` / `UNAVAILABLE` + flags. |
| `ingestion_run_id`    | `INT` → `ingestion_runs.id` | FK back to the run that collected the row.  |

### `data_sources` — registered sources

Model: `app.models.reference.DataSource`. Exactly two seeded rows:
`MOSPI_CPI` (`PUBLIC_DATASET`) and `GOOGLE_FLIGHTS_API` (`LIVE_SCRAPE`).

### `ingestion_runs` — run tracking

Model: `app.models.ingestion.IngestionRun`. One row per collection or
refresh attempt: `data_source_id`, `triggered_by` (`scheduler` or a user
email), `started_at`/`completed_at`, `status`
(`RUNNING` / `SUCCESS` / `SOURCE_UNAVAILABLE` / `FAILED`), row counts
(collected/valid/invalid/suspicious/unavailable), `error_message`, and
`raw_payload_path` for archived pre-normalization payloads.

## Reference & configuration

- **`routes`** (`app.models.reference.Route`) — origin/destination pair
  (unique constraint), `weight`, `distance_tier`, `active`. Seeded from
  `app.services.route_basket.ROUTE_BASKET` (16 routes); admin-editable.
- **`airlines`** (`app.models.reference.Airline`) — derived from
  observed airline names, with a known-IATA map.
- **`booking_window_configs`** — configurable T+n windows (T+1, T+7,
  T+15, T+30, T+45) and their weights.

## Index engine output

- **`index_configs`** (`app.models.index.IndexConfigModel`) — active
  `base_period`, `methodology_version`, `booking_window_weights`,
  `include_suspicious`, `created_by`/notes.
- **`index_runs`** (`app.models.index.IndexRun`) — persisted output of
  `index_engine.compute_index()`: `as_of_period`, `index_value`,
  `change_from_base_pct`, `n_observations_used`, `routes_missing_data`,
  and the `calculation_breakdown` transparency trace.
- **`index_route_contributions`** / **`index_airline_contributions`** —
  per-route and per-airline contribution breakdown for each run.

Auth (`users`) and the rest of the backend follow the same Alembic
baseline; see `backend/app/models/` for the full model set.

## Applied migrations

| Revision | Purpose                                            |
|----------|----------------------------------------------------|
| `0001_initial_schema` | Baseline autogenerate from the models (drift-free). |
| `0002` … `0007`      | Username column, observation indexes, CPI airfare index, intermediate tables (later dropped). |
| `0008_drop_unused_source_tables` | Dropped `scraper_errors`, `fare_searches`, `wpi_atf_index`, `dgca_route_traffic`. |

`alembic upgrade head` applies everything; `alembic check` verifies zero
drift against the models.