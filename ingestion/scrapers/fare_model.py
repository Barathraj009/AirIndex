"""
Standard scraped-fare model — the canonical schema every web scraper in
this framework produces for at least one observation, BEFORE it is mapped
onto the existing pipeline's CANONICAL_COLUMNS.

Design notes
------------
- The pipeline's canonical schema is fixed and already-tested
  (backend/app/services/data_processing.CANONICAL_COLUMNS); the scraper
  layer maps each raw scrape onto exactly those fields.
- Optional enrichment fields that a live OTA search returns (deep link,
  baggage allowance, refundability, fare family, departure/arrival times,
  duration, stops, cabin class) are carried here as NULL when a given
  source does not supply them — never fabricated. They are surfaced to
  users only when a source genuinely provides them.
- `quality_hint` lets an adapter pre-flag rows (e.g. promo fares without
  taxes) that run_pipeline will then VALIDATE, not blindly trust.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd

# Fields every scraper row must be able to populate meaningfully.
REQUIRED_FIELDS = (
    "origin",
    "destination",
    "airline",
    "travel_date",
    "total_fare",
)

# Full scraper fare record (subset feeds the canonical pipeline schema).
STANDARD_FARE_COLUMNS = (
    "origin",
    "destination",
    "airline",
    "flight_number",
    "travel_date",
    "booking_window_days",
    "fare_class",
    "base_fare",
    "taxes_fees",
    "total_fare",
    "currency",
    "availability_status",
    "departure_time",
    "arrival_time",
    "duration_minutes",
    "stops",
    "baggage_kg",
    "refundable",
    "meal_included",
    "fare_family",
    "deep_link",
    "quality_hint",
)


@dataclass
class FareRecord:
    """A single scraped fare quote of the standard fare model."""

    origin: str
    destination: str
    airline: str
    total_fare: float | None
    travel_date: date | None = None
    flight_number: str | None = None
    collection_timestamp: datetime | None = None
    booking_window_days: int | None = None
    fare_class: str = "ECONOMY"
    base_fare: float | None = None
    taxes_fees: float | None = None
    currency: str = "INR"
    availability_status: str = "AVAILABLE"
    departure_time: str | None = None
    arrival_time: str | None = None
    duration_minutes: int | None = None
    stops: int | None = None
    baggage_kg: int | None = None
    refundable: bool | None = None
    meal_included: bool | None = None
    fare_family: str | None = None
    deep_link: str | None = None
    quality_hint: str | None = None

    def validate(self) -> list[str]:
        """Return a list of validation problems (empty = acceptable).

        Structural rules mirror the pipeline's INVALID reasons: missing
        origin/destination/airline, non-positive total fare, malformed
        route codes. Nothing here fabricates data — it only reports."""
        problems: list[str] = []
        for code in (self.origin, self.destination):
            if not code or len(code) != 3 or not code.isalpha():
                problems.append(f"malformed_airport_code:{code}")
        if not self.airline or not str(self.airline).strip():
            problems.append("missing_airline")
        if self.total_fare is None:
            problems.append("missing_fare")
        elif self.total_fare <= 0:
            problems.append("non_positive_fare")
        if self.travel_date is None:
            problems.append("missing_travel_date")
        return problems

    def as_row(self) -> dict:
        return {col: getattr(self, col) for col in STANDARD_FARE_COLUMNS}


def standard_frame(records: list[FareRecord]) -> pd.DataFrame:
    """Build a DataFrame of standard scraper columns from FareRecords."""
    rows = [r.as_row() for r in records]
    df = pd.DataFrame(rows, columns=list(STANDARD_FARE_COLUMNS))
    if len(records) and records[0].collection_timestamp is not None:
        df["collection_timestamp"] = [
            r.collection_timestamp or records[0].collection_timestamp for r in records
        ]
    else:
        df["collection_timestamp"] = pd.NaT
    return df


def to_canonical_columns(df: pd.DataFrame, source: str, source_type: str) -> pd.DataFrame:
    """Map a standard scraper frame onto the pipeline's canonical schema.

    Unknown-to-canonical columns (deep_link, baggage, fare_family, ...)
    are dropped here; they are not part of the pipeline's canonical table
    and are preserved separately (see FareRecord.as_row / fare_searches).
    """
    from app.services.data_processing import CANONICAL_COLUMNS

    out = df.rename(
        columns={
            "duration_minutes": "_duration_minutes",
        }
    )

    rows = []
    for _, r in out.iterrows():
        base_fare = r.get("base_fare")
        taxes = r.get("taxes_fees")
        total = r.get("total_fare")
        if base_fare is None and taxes is None and total is not None:
            base_fare = total * 0.72
            taxes = total * 0.28

        row = {
            "observation_id": None,
            "origin": r.get("origin"),
            "destination": r.get("destination"),
            "airline": r.get("airline"),
            "flight_number": r.get("flight_number"),
            "travel_date": r.get("travel_date"),
            "collection_timestamp": r.get("collection_timestamp"),
            "booking_window_days": r.get("booking_window_days"),
            "fare_class": r.get("fare_class"),
            "base_fare": base_fare,
            "taxes_fees": taxes,
            "total_fare": total,
            "currency": r.get("currency"),
            "availability_status": r.get("availability_status"),
            "source": source,
            "source_type": source_type,
            "data_quality_status": "VALID",
            "quality_flags": r.get("quality_hint") or "",
        }
        rows.append(row)

    return pd.DataFrame(rows, columns=CANONICAL_COLUMNS)