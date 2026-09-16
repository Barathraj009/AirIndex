"""
Bootstrap — seeds ONLY reference data needed for the app to run:
routes, the MoSPI data source, default admin user, and an active index
configuration.

NO synthetic/demo fare observations are loaded. The CPI airfare index
table is populated at server startup by the lifespan hook in main.py
(fetching live data from api.mospi.gov.in).

If the observation/reference tables are empty, the bundled Google Flights
and MoSPI replay captures (real, provenance-labelled records from the
licensed Google Flights feed and api.mospi.gov.in) are loaded so that the
deployed app always renders real values — no external key required.

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

# The route basket used by index_engine (weight = share of all-India
# domestic air passenger traffic). These are the routes covered by the
# MoSPI CPI airfare component (07.3.3.1).
ROUTE_BASKET = {
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
            print(f"Seeded {len(ROUTE_BASKET)} routes.")

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

        if db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first() is None:  # noqa: E712
            db.add(IndexConfigModel(
                base_period="2026-01",
                methodology_version=METHODOLOGY_VERSION,
                is_active=True,
                created_by="bootstrap_reference.py",
            ))
            db.commit()
            print("Seeded active index config (base_period=2026-01).")

        _load_google_flights_replay(db)
        _load_mospi_cpi_replay(db)

        db.commit()
        print("Bootstrap complete.")
    finally:
        db.close()


def _load_google_flights_replay(db):
        """Load the bundled Google Flights captures if none observed yet, so
        the dashboard always renders real fare values (no API key required
        on first boot)."""
        if db.query(FareObservation).count() > 0:
            print(f"fare_observations already populated ({db.query(FareObservation).count()} rows); keeping existing data.")
            return

        import pandas as pd

        from app.services.data_processing import run_pipeline

        raw = pd.DataFrame(google_flights_replay())
        for col in ("booking_window_days", "base_fare", "taxes_fees", "total_fare"):
            if col in raw.columns:
                raw[col] = pd.to_numeric(raw[col], errors="coerce")
        clean_df, report = run_pipeline(raw, source="GOOGLE_FLIGHTS_API", source_type="LIVE_SCRAPE")

        if db.query(Airline).count() == 0:
            known_iata = {"IndiGo": "6E", "Air India": "AI", "Air India Express": "IX",
                          "Akasa Air": "QP", "SpiceJet": "SG", "Vistara": "UK"}
            for name in sorted(clean_df["airline"].dropna().unique()):
                db.add(Airline(name=name, iata_code=known_iata.get(name), active=True))
            db.commit()
            print(f"Seeded {db.query(Airline).count()} airlines from observed data.")

        rows = clean_df.to_dict("records")
        cleaned_rows = records_json_safe([
            {k: r[k] for k in r if k in FareObservation.__table__.columns.keys()}
            for r in rows
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
        print(f"Seeded {len(rows)} Google Flights fare observations ({report.as_dict()}).")


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