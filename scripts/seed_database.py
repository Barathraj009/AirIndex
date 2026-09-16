"""Seed script — loads the route basket, real data sources, a default admin
user, and an active index configuration into the database.

Usage (once `pip install -r backend/requirements.txt` succeeds):

    PYTHONPATH=.:./backend python3 scripts/seed_database.py
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.database import engine, SessionLocal
from app.core.json_safe import records_json_safe
from app.core.security import hash_password
from app.models import Base, Route, DataSource, User, IndexConfigModel, Airline
from app.services.route_basket import ROUTE_BASKET
from app.services.replay_data import google_flights_replay
from app.services.data_processing import run_pipeline
from app.models.observations import FareObservation
from app.services.index_engine import METHODOLOGY_VERSION


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Route).count() == 0:
            for route, (weight, tier) in ROUTE_BASKET.items():
                origin, dest = route.split("-")
                db.add(Route(origin=origin, destination=dest, weight=weight, distance_tier=tier))
            print(f"Seeded {len(ROUTE_BASKET)} routes.")

        sources_to_seed = [
            ("GOOGLE_FLIGHTS_API", "LIVE_SCRAPE"),
            ("MOSPI_CPI", "PUBLIC_DATASET"),
        ]
        for sname, stype in sources_to_seed:
            if db.query(DataSource).filter(DataSource.name == sname).first() is None:
                db.add(DataSource(name=sname, source_type=stype, active=True))
                print(f"Seeded {sname} data source.")

        admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@airindex.gov.in")
        admin_password = os.getenv("SEED_ADMIN_PASSWORD", "change-me-immediately")

        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            if admin_password in ("change-me-immediately", "analyst123", "viewer123", "", "1234"):
                db.close()
                raise RuntimeError(
                    "Refusing to seed in production with a default admin password. "
                    "Set SEED_ADMIN_PASSWORD to a strong unique value."
                )

        users_to_seed = [
            (admin_email, admin_password, "ADMIN"),
            ("analyst@airindex.gov.in", "analyst123", "ANALYST"),
            ("viewer@airindex.gov.in", "viewer123", "VIEWER"),
        ]
        for uemail, upass, urole in users_to_seed:
            if db.query(User).filter(User.email == uemail).first() is None:
                db.add(User(email=uemail, hashed_password=hash_password(upass), role=urole))
                print(f"Seeded user ({uemail}, {urole}).")

        import pandas as pd

        raw = pd.DataFrame(google_flights_replay())
        # Coerce numeric replay columns (CSV round-trips them as strings).
        for col in ("booking_window_days", "base_fare", "taxes_fees", "total_fare"):
            if col in raw.columns:
                raw[col] = pd.to_numeric(raw[col], errors="coerce")
        clean_df, report = run_pipeline(raw, source="GOOGLE_FLIGHTS_API", source_type="LIVE_SCRAPE")
        rows = clean_df.to_dict("records")

        if db.query(Airline).count() == 0:
            known_iata = {"IndiGo": "6E", "Air India": "AI", "Air India Express": "IX",
                          "Akasa Air": "QP", "SpiceJet": "SG", "Vistara": "UK"}
            for name in sorted(clean_df["airline"].dropna().unique()):
                db.add(Airline(name=name, iata_code=known_iata.get(name), active=True))
            db.commit()
            print(f"Seeded {db.query(Airline).count()} airlines from observed data.")

        if db.query(FareObservation).count() == 0:
            cleaned_rows = records_json_safe([
                {k: r[k] for k in r if k in FareObservation.__table__.columns.keys()}
                for r in rows
            ])
            coerced_rows = []
            for r in cleaned_rows:
                r = dict(r)
                td = r.get("travel_date")
                if isinstance(td, str):
                    r["travel_date"] = date.fromisoformat(td[:10])
                ts = r.get("collection_timestamp")
                if isinstance(ts, str):
                    r["collection_timestamp"] = datetime.fromisoformat(
                        ts.replace("Z", "+00:00")
                    )
                coerced_rows.append(r)
            db.bulk_insert_mappings(FareObservation, coerced_rows)
            db.commit()
            print(f"Seeded {len(rows)} fare observations ({report.as_dict()}).")
        else:
            print(f"fare_observations already populated ({db.query(FareObservation).count()} rows); skipping.")

        if db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first() is None:  # noqa: E712
            periods = sorted(clean_df["travel_date"].str[:7].unique())
            db.add(IndexConfigModel(
                base_period=periods[0], methodology_version=METHODOLOGY_VERSION,
                is_active=True, created_by="seed_script",
            ))
            print(f"Seeded active index config with base_period={periods[0]}.")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
