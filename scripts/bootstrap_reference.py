"""
Bootstrap — seeds ONLY reference data needed for the app to run:
routes, the MoSPI data source, default admin user, and an active index
configuration.

NO synthetic/demo fare observations are loaded. The CPI airfare index
table is populated at server startup by the lifespan hook in main.py
(fetching live data from api.mospi.gov.in).

If the observation/reference tables are empty, the bundled Google Flights
and MoSPI captures (real, provenance-labelled records from the
licensed Google Flights feed and api.mospi.gov.in) are loaded so that the
deployed app always renders real values — no external key required. On a
pre-populated database, any missing Google Flights replay departure dates
are backfilled — additive only, never overwriting or duplicating existing
rows.

Usage:
    PYTHONPATH=./backend python scripts/bootstrap_reference.py

Environment:
    DATABASE_URL      - Postgres connection string
    SEED_ADMIN_EMAIL  - admin email (default admin@airindex.gov.in)
    SEED_ADMIN_PASSWORD - admin password (required in production)
"""

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.database import SessionLocal, engine
from app.core.json_safe import records_json_safe
from app.core.security import hash_password
from app.services.data_processing import CANONICAL_COLUMNS  # noqa: F401 (schema surface)
from app.models import Base, Route, DataSource, User, IndexConfigModel, Airline
from app.models.cpi import CpiAirfareIndex
from app.models.observations import FareObservation
from app.services.index_engine import METHODOLOGY_VERSION
from app.services.replay_data import google_flights_replay, mospi_cpi_replay
from app.services.route_basket import ROUTE_BASKET

DATA_SOURCES = [
    ("MOSPI_CPI", "PUBLIC_DATASET"),
    # Licensed live fare feed (Google Flights via RapidAPI, gds_adapter).
    # Seeded so the scheduled/manual ingestion can collect real fares in
    # production; requires RAPIDAPI_KEY in the environment.
    ("GOOGLE_FLIGHTS_API", "LIVE_SCRAPE"),
]


def bootstrap():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Route).count() == 0:
            for route, (weight, tier) in ROUTE_BASKET.items():
                origin, dest = route.split("-")
                db.add(Route(origin=origin, destination=dest, weight=weight, distance_tier=tier))
            db.commit()
            print(f"Seeded {len(ROUTE_BASKET)} routes (canonical basket, sum={sum(w for w, _ in ROUTE_BASKET.values()):.2f}).")

        for sname, stype in DATA_SOURCES:
            if db.query(DataSource).filter(DataSource.name == sname).first() is None:
                db.add(DataSource(name=sname, source_type=stype, active=True))
                db.commit()
                print(f"Seeded {sname} data source.")

        admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@airindex.gov.in")
        admin_password = os.getenv("SEED_ADMIN_PASSWORD", "change-me-immediately")

        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            if admin_password in ("change-me-immediately", "analyst123", "viewer123", "", "1234"):
                db.close()
                raise RuntimeError(
                    "Refusing to bootstrap in production with a default admin "
                    "password. Set SEED_ADMIN_PASSWORD to a strong unique value."
                )

        if db.query(User).filter(User.email == admin_email).first() is None:
            db.add(User(email=admin_email, hashed_password=hash_password(admin_password), role="ADMIN"))
            db.commit()
            print(f"Seeded admin user ({admin_email}, ADMIN).")

        _load_google_flights_replay(db)
        _load_mospi_cpi_replay(db)

        if db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first() is None:  # noqa: E712
            observed = _observed_base_period(db)
            db.add(IndexConfigModel(
                base_period=observed or "2026-01",
                methodology_version=METHODOLOGY_VERSION,
                is_active=True,
                created_by="bootstrap_reference.py",
            ))
            print(f"Seeded active index config (base_period={observed or '2026-01'}).")

        _reconcile_legacy_basket(db)
        _reconcile_config_base_period(db)

        db.commit()
        print("Bootstrap complete.")
    finally:
        db.close()


def _observed_base_period(db) -> str | None:
    """Earliest period that has fare observations — the base period must be a
    period where real data exists, otherwise the index cannot be computed."""
    from app.models.observations import FareObservation
    from sqlalchemy import func

    row = (
        db.query(func.min(FareObservation.travel_date))
        .filter(FareObservation.data_quality_status.in_(["VALID", "SUSPICIOUS"]))
        .scalar()
    )
    if row is None:
        return None
    return row.strftime("%Y-%m")


# The legacy basket baked into databases seeded before canonical unification.
# Fingerprint match is required (exact routes + weights + tiers) so we never
# overwrite a basket an admin has intentionally customized.
_LEGACY_BASKET = {
    "DEL-BOM": (0.13, "MEDIUM"),
    "DEL-BLR": (0.11, "MEDIUM"),
    "BOM-BLR": (0.09, "MEDIUM"),
    "DEL-CCU": (0.08, "SHORT"),
    "DEL-HYD": (0.09, "SHORT"),
    "BLR-HYD": (0.07, "SHORT"),
    "DEL-MAA": (0.08, "MEDIUM"),
    "BOM-MAA": (0.07, "MEDIUM"),
    "DEL-GOI": (0.05, "MEDIUM"),
    "BOM-GOI": (0.04, "MEDIUM"),
    "BLR-CCU": (0.04, "LONG"),
    "DEL-TRV": (0.04, "LONG"),
    "BOM-HYD": (0.03, "SHORT"),
    "DEL-PNQ": (0.02, "SHORT"),
    "BLR-MAA": (0.02, "SHORT"),
    "BOM-CCU": (0.02, "LONG"),
}


def _reconcile_legacy_basket(db) -> None:
    """One-time migration: replace the legacy basket (sum 0.98, MEDIUM/SHORT/
    LONG tiers) with the canonical basket when the DB still holds an exact
    legacy fingerprint. Does nothing if routes were customized."""
    from app.models import Route

    db_routes = {
        f"{r.origin}-{r.destination}": (round(r.weight, 4), (r.distance_tier or "").upper())
        for r in db.query(Route).all()
    }
    expected = {k: v for k, v in _LEGACY_BASKET.items()}
    if db_routes != expected:
        return
    db.query(Route).delete()
    for route, (weight, tier) in ROUTE_BASKET.items():
        origin, dest = route.split("-")
        db.add(Route(origin=origin, destination=dest, weight=weight, distance_tier=tier))
    print("Reconciled legacy route basket -> canonical basket (sum 1.00).")


def _reconcile_config_base_period(db) -> None:
    """One-time migration: fix a bootstrap hardcoded base_period (2026-01)
    that predates any fare data. Re-base to the first observed period."""
    from app.models.index import IndexConfigModel

    active = db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first()  # noqa: E712
    observed = _observed_base_period(db)
    if active is None or observed is None:
        return
    if active.base_period == "2026-01" and active.base_period != observed:
        active.base_period = observed
        print(f"Reconciled config base_period: 2026-01 -> {observed}.")


def _load_google_flights_replay(db):
    """Load the bundled real Google Flights captures.

    Fresh DB (no observations yet): load every replay capture so the
    dashboard renders real fares with no external key.

    Pre-populated DB (older database seeded before the real captures
    existed, or one fed only by live runs): backfill just the
    (origin, destination, airline, travel_date) keys that are missing, so
    the real replay departure dates are never absent — and existing rows
    are never overwritten or duplicated. Idempotent: a second run adds
    nothing.
    """
    import pandas as pd

    from app.services.data_processing import run_pipeline

    raw = pd.DataFrame(google_flights_replay())
    for col in ("booking_window_days", "base_fare", "taxes_fees", "total_fare"):
        if col in raw.columns:
            raw[col] = pd.to_numeric(raw[col], errors="coerce")
    clean_df, report = run_pipeline(raw, source="GOOGLE_FLIGHTS_API", source_type="LIVE_SCRAPE")

    quality = (FareObservation.data_quality_status.in_(("VALID", "SUSPICIOUS")))
    existing = db.query(
        FareObservation.observation_id,
        FareObservation.origin,
        FareObservation.destination,
        FareObservation.airline,
        FareObservation.travel_date,
    ).filter(quality).all()
    existing_ids = {row[0] for row in existing}
    existing_keys = {(row[1], row[2], row[3], row[4]) for row in existing}

    if db.query(Airline).count() == 0:
        known_iata = {"IndiGo": "6E", "Air India": "AI", "Air India Express": "IX",
                      "Akasa Air": "QP", "SpiceJet": "SG", "Vistara": "UK"}
        for name in sorted(clean_df["airline"].dropna().unique()):
            db.add(Airline(name=name, iata_code=known_iata.get(name), active=True))
        db.commit()
        print(f"Seeded {db.query(Airline).count()} airlines from observed data.")

    rows = clean_df.to_dict("records")
    missing = []
    for r in rows:
        if r.get("observation_id") in existing_ids:
            continue
        td = r.get("travel_date")
        if isinstance(td, str):
            td = date.fromisoformat(td[:10])
        elif hasattr(td, "date"):
            td = td.date()
        key = (r.get("origin"), r.get("destination"), r.get("airline"), td)
        if key in existing_keys:
            continue
        existing_ids.add(r.get("observation_id"))
        existing_keys.add(key)
        missing.append(r)

    if not missing:
        print(f"fare_observations already populated ({len(existing_keys)} route/airline/date keys); replay needs no backfill.")
        return

    cleaned_rows = records_json_safe([
        {k: r[k] for k in r if k in FareObservation.__table__.columns.keys()}
        for r in missing
    ])
    coerced = []
    for r in cleaned_rows:
        r = dict(r)
        td = r.get("travel_date")
        if isinstance(td, str):
            r["travel_date"] = date.fromisoformat(td[:10])
        ts = r.get("collection_timestamp")
        if isinstance(ts, str):
            r["collection_timestamp"] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        coerced.append(r)
    db.bulk_insert_mappings(FareObservation, coerced)
    db.commit()
    print(f"Backfilled {len(missing)} missing Google Flights fare observations "
          f"(total now {db.query(FareObservation).count()}; {report.as_dict()}).")


def _load_mospi_cpi_replay(db):
        """Load the bundled MoSPI CPI captures if the table is empty, so the
        CPI anchor renders even before the first scheduled live refresh."""
        if db.query(CpiAirfareIndex).count() > 0:
            print(f"cpi_airfare_index already populated ({db.query(CpiAirfareIndex).count()} rows); keeping existing data.")
            return

        rows = mospi_cpi_replay()
        if not rows:
            return
        bulk = []
        now = datetime.now(timezone.utc)
        for r in rows:
            period = r.get("period") or r.get("data_date", "")[:7]
            data_date = r.get("data_date") or period
            bulk.append({
                "period": period,
                "data_date": date.fromisoformat(str(data_date)[:10]),
                "airfare_index": float(r["airfare_index"]),
                "transport_index": float(r["transport_index"]) if r.get("transport_index") else None,
                "general_index": float(r["general_index"]) if r.get("general_index") else None,
                "inflation_yoy": float(r["inflation_yoy"]) if r.get("inflation_yoy") else None,
                "inflation_mom": float(r["inflation_mom"]) if r.get("inflation_mom") else None,
                "source": "MOSPI_CPI",
                "source_url": "https://esankhyiki.mospi.gov.in",
                "cpi_code": "07.3.3.1",
                "base_year": "2024=100",
                "fetched_at": now,
                "created_at": now,
            })
        db.bulk_insert_mappings(CpiAirfareIndex, bulk)
        db.commit()
        print(f"Seeded {len(bulk)} MoSPI CPI airfare index rows.")


if __name__ == "__main__":
    bootstrap()