# Data Source Status (2026-09)

The product serves exactly **two real data sources**. Both are live and
feed the combined airfare index.

| Source             | Source type    | Status | What it provides                                                          |
|--------------------|----------------|--------|--------------------------------------------------------------------------|
| `MOSPI_CPI`        | `PUBLIC_DATASET` | LIVE | Official MoSPI CPI airfare index, code 07.3.3.1 (domestic air transport), base 2024=100, published monthly. |
| `GOOGLE_FLIGHTS_API`| `LIVE_SCRAPE`   | LIVE | Live Google Flights calendar fares per route via the licensed RapidAPI feed (`google-flights8.p.rapidapi.com`, Basic $0 plan). |

## MOSPI_CPI — official airfare index

- Adapter: `ingestion/adapters/mospi_cpi.py`.
- Fetch: `https://api.mospi.gov.in/api/cpi/getCPIData` (base year 2024,
  All-India combined sector).
- Target code: **07.3.3.1** ("Passenger transport by air, domestic").
- Cadence: refreshed at startup and on the scheduled ingestion cron;
  MoSPI publishes monthly around the 12th.
- Stored in: `cpi_airfare_index` (period, `airfare_index`, YoY/MoM
  inflation, transport/division indexes, provenance).
- Failure: if MoSPI is unreachable, the last known series stays in the
  table and the refresh is reported, never fabricated.

## GOOGLE_FLIGHTS_API — live fare feed

- Adapter: `ingestion/adapters/gds_adapter.py`.
- API: RapidAPI provider `google-flights8`, host
  `google-flights8.p.rapidapi.com`, `price-graph/one-way` endpoint.
- One call per route returns the ~91-day calendar across all booking
  windows; near-horizon sparse responses trigger a short-horizon
  backfill.
- Prices arrive in USD and are converted to INR at `FX_RATE_USD_INR`.
- Requires `RAPIDAPI_KEY` in the environment; without it the feed stays
  inert and the source reports `SOURCE_UNAVAILABLE` rather than
  fabricating data.
- Stored in: `fare_observations` (source `GOOGLE_FLIGHTS_API`,
  source_type `LIVE_SCRAPE`).
- Cadence: daily (≈180 requests/month on 6 routes at the default
  `INGESTION_SCHEDULE_CRON`).

## Unavailable-verdict behavior

When either source can't be reached, its adapter raises
`SourceUnavailableError` and the corresponding ingestion run is recorded
as `SOURCE_UNAVAILABLE` — the UI/API show **SOURCE UNAVAILABLE** rather
than silently dropping or inventing data. See `docs/troubleshooting.md`
for how to diagnose each source.