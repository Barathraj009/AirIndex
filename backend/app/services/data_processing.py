"""
AirIndex India — Data Processing Module
=========================================
Pure-Python / pandas-numpy logic for turning raw, heterogeneous fare
observations (scraped or demo-generated) into a validated, normalized
dataset ready for the Airfare Price Index Engine.

This module is intentionally framework-agnostic (no FastAPI / SQLAlchemy
imports) so it can be:
  1. Unit tested in isolation (see tests/test_data_processing.py)
  2. Reused unchanged by both the FastAPI production service layer
     (backend/app/api/*) and the lightweight dev_demo Flask reference
     server.

Data-quality statuses
----------------------
VALID        - passed all checks, safe to use in index calculation
SUSPICIOUS   - passed structural checks but flagged by outlier detection;
               retained but down-weighted / excluded depending on config
INVALID      - failed structural/business-rule validation (negative fare,
               missing mandatory field, malformed route, etc.)
UNAVAILABLE  - the source explicitly reported no fare (sold out, flight
               cancelled, or SOURCE UNAVAILABLE from the adapter layer)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Canonical schema
# ---------------------------------------------------------------------------

CANONICAL_COLUMNS = [
    "observation_id",       # stable hash of the raw observation (dedup key)
    "origin",                # IATA code, e.g. DEL
    "destination",           # IATA code, e.g. BOM
    "airline",                # canonical airline name
    "flight_number",
    "travel_date",           # date of the flight
    "collection_timestamp",  # when the observation was captured
    "booking_window_days",   # T+n at time of collection (n = travel_date - collection date)
    "fare_class",
    "base_fare",
    "taxes_fees",
    "total_fare",
    "currency",
    "availability_status",   # AVAILABLE / SOLD_OUT / CANCELLED / UNKNOWN
    "source",                 # e.g. "DEMO_SIMULATED", "INDIGO_WEB", "PUBLIC_DATA"
    "source_type",             # LIVE_SCRAPE / PUBLIC_DATASET / DEMO_SIMULATED
    "data_quality_status",   # VALID / SUSPICIOUS / INVALID / UNAVAILABLE
    "quality_flags",          # semicolon-joined list of reasons
]


class DataQualityStatus(str, Enum):
    VALID = "VALID"
    SUSPICIOUS = "SUSPICIOUS"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"


class SourceType(str, Enum):
    LIVE_SCRAPE = "LIVE_SCRAPE"
    PUBLIC_DATASET = "PUBLIC_DATASET"
    DEMO_SIMULATED = "DEMO_SIMULATED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


VALID_IATA = {
    "DEL", "BOM", "BLR", "MAA", "CCU", "HYD", "PNQ", "GOI", "COK", "AMD",
    "JAI", "LKO", "IXC", "GAU", "IXB", "PAT", "BBI", "NAG", "VNS", "IDR",
    "SXR", "IXR", "RPR", "TRV", "IXM", "STV", "UDR", "IXJ", "ATQ", "VTZ",
}

REQUIRED_FIELDS = ["origin", "destination", "airline", "travel_date",
                    "collection_timestamp", "total_fare"]


def _obs_hash(row: dict) -> str:
    """Deterministic id used for de-duplication: same underlying fare quote
    (same route/airline/flight/travel-date/collection-timestamp/fare) always
    hashes identically, regardless of which adapter produced it."""
    key = "|".join(str(row.get(k, "")) for k in [
        "origin", "destination", "airline", "flight_number",
        "travel_date", "collection_timestamp", "fare_class", "total_fare",
    ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


@dataclass
class QualityReport:
    total_rows: int = 0
    valid: int = 0
    suspicious: int = 0
    invalid: int = 0
    unavailable: int = 0
    duplicates_removed: int = 0
    outliers_iqr: int = 0
    outliers_mad: int = 0
    issues: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "valid": self.valid,
            "suspicious": self.suspicious,
            "invalid": self.invalid,
            "unavailable": self.unavailable,
            "duplicates_removed": self.duplicates_removed,
            "outliers_iqr": self.outliers_iqr,
            "outliers_mad": self.outliers_mad,
            "valid_pct": round(100 * self.valid / self.total_rows, 2) if self.total_rows else 0.0,
            "issues_sample": self.issues[:20],
        }


def normalize_raw_observations(raw_df: pd.DataFrame, source: str, source_type: str) -> pd.DataFrame:
    """Map a source-specific raw dataframe (already produced by an adapter's
    `.to_common_format()`) onto CANONICAL_COLUMNS. Adapters are responsible
    for mapping their own field names into the canonical ones *before*
    calling this function; this function fills in anything still missing,
    computes derived fields, and assigns the observation_id.
    """
    df = raw_df.copy()

    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    df["source"] = df["source"].fillna(source)
    df["source_type"] = df["source_type"].fillna(source_type)

    # Derive booking_window_days if not already supplied
    def _window(r):
        if pd.notna(r.get("booking_window_days")):
            return r["booking_window_days"]
        try:
            td = pd.to_datetime(r["travel_date"]).date()
            ct = pd.to_datetime(r["collection_timestamp"]).date()
            return (td - ct).days
        except Exception:
            return np.nan

    df["booking_window_days"] = df.apply(_window, axis=1)

    df["total_fare"] = pd.to_numeric(df["total_fare"], errors="coerce")
    df["base_fare"] = pd.to_numeric(df["base_fare"], errors="coerce")
    df["taxes_fees"] = pd.to_numeric(df["taxes_fees"], errors="coerce")

    # If total_fare missing but base+taxes present, derive it
    mask = df["total_fare"].isna() & df["base_fare"].notna() & df["taxes_fees"].notna()
    df.loc[mask, "total_fare"] = df.loc[mask, "base_fare"] + df.loc[mask, "taxes_fees"]

    df["currency"] = df["currency"].fillna("INR")
    df["availability_status"] = df["availability_status"].fillna("UNKNOWN")

    df["observation_id"] = df.apply(lambda r: _obs_hash(r.to_dict()), axis=1)

    return df[CANONICAL_COLUMNS]


def _structural_validation(df: pd.DataFrame) -> pd.DataFrame:
    """Flags rows that fail basic business rules as INVALID / UNAVAILABLE."""
    df = df.copy()
    flags = [[] for _ in range(len(df))]
    status = [DataQualityStatus.VALID.value] * len(df)

    for i, row in enumerate(df.itertuples(index=False)):
        r = row._asdict()

        if r["availability_status"] in ("SOLD_OUT", "CANCELLED"):
            status[i] = DataQualityStatus.UNAVAILABLE.value
            flags[i].append(f"availability={r['availability_status']}")
            continue

        for f in REQUIRED_FIELDS:
            if pd.isna(r.get(f)) or r.get(f) in ("", None):
                flags[i].append(f"missing:{f}")

        if r.get("origin") not in VALID_IATA:
            flags[i].append("unrecognized_origin")
        if r.get("destination") not in VALID_IATA:
            flags[i].append("unrecognized_destination")
        if r.get("origin") == r.get("destination"):
            flags[i].append("origin_equals_destination")

        total_fare = r.get("total_fare")
        if pd.isna(total_fare):
            flags[i].append("missing_total_fare")
        elif total_fare <= 0:
            flags[i].append("non_positive_fare")
        elif total_fare < 800:
            # Domestic Indian one-way fares are not realistically below this
            flags[i].append("implausibly_low_fare")
        elif total_fare > 150000:
            flags[i].append("implausibly_high_fare")

        bw = r.get("booking_window_days")
        if pd.isna(bw) or bw < 0:
            flags[i].append("invalid_booking_window")

        if flags[i]:
            # any structural flag -> INVALID (cannot be used at all)
            hard_fail_markers = (
                "missing:", "unrecognized_", "origin_equals_destination",
                "missing_total_fare", "non_positive_fare",
                "implausibly_low_fare", "implausibly_high_fare",
                "invalid_booking_window",
            )
            if any(any(fl.startswith(m) for m in hard_fail_markers) for fl in flags[i]):
                status[i] = DataQualityStatus.INVALID.value

    df["data_quality_status"] = status
    df["quality_flags"] = ["; ".join(f) for f in flags]
    return df


def detect_outliers_iqr(series: pd.Series, k: float = 1.5) -> pd.Series:
    """Classic Tukey IQR fence. Returns a boolean mask, True = outlier."""
    clean = series.dropna()
    if len(clean) < 4:
        return pd.Series(False, index=series.index)
    q1, q3 = np.percentile(clean, [25, 75])
    iqr = q3 - q1
    lower, upper = q1 - k * iqr, q3 + k * iqr
    return (series < lower) | (series > upper)


def detect_outliers_mad(series: pd.Series, threshold: float = 3.5) -> pd.Series:
    """Median Absolute Deviation based robust outlier detection
    (Iglewicz & Hoaglin modified z-score)."""
    clean = series.dropna()
    if len(clean) < 4:
        return pd.Series(False, index=series.index)
    median = np.median(clean)
    mad = np.median(np.abs(clean - median))
    if mad == 0:
        return pd.Series(False, index=series.index)
    modified_z = 0.6745 * (series - median) / mad
    return modified_z.abs() > threshold


def run_outlier_detection(df: pd.DataFrame, group_cols=("origin", "destination", "booking_window_days")) -> pd.DataFrame:
    """Runs IQR + MAD outlier detection *within* each route/booking-window
    group (fares differ hugely by route, so global thresholds would be
    meaningless). A row is SUSPICIOUS if either method flags it, unless it
    is already INVALID/UNAVAILABLE.
    """
    df = df.copy()
    df["is_outlier_iqr"] = False
    df["is_outlier_mad"] = False

    eligible = df["data_quality_status"] == DataQualityStatus.VALID.value

    for _, idx in df[eligible].groupby(list(group_cols)).groups.items():
        sub = df.loc[idx, "total_fare"]
        df.loc[idx, "is_outlier_iqr"] = detect_outliers_iqr(sub)
        df.loc[idx, "is_outlier_mad"] = detect_outliers_mad(sub)

    outlier_mask = eligible & (df["is_outlier_iqr"] | df["is_outlier_mad"])
    df.loc[outlier_mask, "data_quality_status"] = DataQualityStatus.SUSPICIOUS.value

    def _append_flag(row):
        extra = []
        if row["is_outlier_iqr"]:
            extra.append("outlier_iqr")
        if row["is_outlier_mad"]:
            extra.append("outlier_mad")
        if not extra:
            return row["quality_flags"]
        existing = row["quality_flags"]
        return (existing + "; " + "; ".join(extra)) if existing else "; ".join(extra)

    df["quality_flags"] = df.apply(_append_flag, axis=1)
    return df


def deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    before = len(df)
    df = df.sort_values("collection_timestamp").drop_duplicates(
        subset=["observation_id"], keep="last"
    )
    return df, before - len(df)


def run_pipeline(raw_df: pd.DataFrame, source: str, source_type: str) -> tuple[pd.DataFrame, QualityReport]:
    """Full pipeline: normalize -> dedup -> structural validation ->
    outlier detection -> quality report. This is the single entry point
    both the FastAPI ingestion service and the dev_demo server call."""
    report = QualityReport()

    df = normalize_raw_observations(raw_df, source=source, source_type=source_type)
    df, dup_removed = deduplicate(df)
    report.duplicates_removed = dup_removed

    df = _structural_validation(df)
    df = run_outlier_detection(df)

    report.total_rows = len(df)
    counts = df["data_quality_status"].value_counts().to_dict()
    report.valid = counts.get(DataQualityStatus.VALID.value, 0)
    report.suspicious = counts.get(DataQualityStatus.SUSPICIOUS.value, 0)
    report.invalid = counts.get(DataQualityStatus.INVALID.value, 0)
    report.unavailable = counts.get(DataQualityStatus.UNAVAILABLE.value, 0)
    report.outliers_iqr = int(df["is_outlier_iqr"].sum())
    report.outliers_mad = int(df["is_outlier_mad"].sum())
    report.issues = df.loc[df["quality_flags"] != "", "quality_flags"].value_counts().index.tolist()

    return df, report
