"""Offline replay of real captured data, bundled with the repository.

The product serves ONLY real data: live Google Flights fares (via RapidAPI /
gds_adapter) and the official MoSPI CPI airfare index (07.3.3.1). The CSVs in
``backend/app/data/`` are snapshots of real collected/published records:

* ``google_flights_replay.csv`` — 30 fare observations collected 2026-09-16
  from the licensed Google Flights feed (RapidAPI, google-flights8 price
  graph), all VALID. Fares are stored in INR (converted from USD at
  FX_RATE_USD_INR=90.0 during capture); the calendar-price endpoint returns a
  per-day cheapest fare, so airline is reported as MULTI (aggregate) by design.
* ``mospi_cpi_replay.csv`` — 32 months (2024-01..2026-08) of the official
  MoSPI airfare CPI series (code 07.3.3.1, base 2024=100) as published by
  api.mospi.gov.in / esankhyiki.mospi.gov.in.

Fresh databases (local dev, CI, the integration-test schema) replay these
records so the whole pipeline runs deterministically offline with real,
provenance-labelled data. Live deployments never replay — they collect via
the real adapters and the scheduled MoSPI refresh.
"""

import csv
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_GOOGLE_FLIGHTS_REPLAY = "google_flights_replay.csv"
_MOSPI_CPI_REPLAY = "mospi_cpi_replay.csv"


def _read_csv(filename: str) -> list[dict]:
    path = _DATA_DIR / filename
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def google_flights_replay() -> list[dict]:
    """Return the bundled Google Flights observations (real captures)."""
    return _read_csv(_GOOGLE_FLIGHTS_REPLAY)


def mospi_cpi_replay() -> list[dict]:
    """Return the bundled MoSPI CPI airfare index records (real publishes)."""
    return _read_csv(_MOSPI_CPI_REPLAY)


def google_flights_replay_path() -> Path:
    return _DATA_DIR / _GOOGLE_FLIGHTS_REPLAY


def mospi_cpi_replay_path() -> Path:
    return _DATA_DIR / _MOSPI_CPI_REPLAY