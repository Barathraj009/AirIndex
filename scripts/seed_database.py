"""
Seed script — loads the route basket, demo fare data, a default admin
user, and an active index configuration into the database.

Usage (once `pip install -r backend/requirements.txt` succeeds and
Postgres is running / migrated):

    PYTHONPATH=.:./backend python3 scripts/seed_database.py

This is written against the real SQLAlchemy models
(backend/app/models/*.py) and was execution-verified during the 2026-09
rebuild (alembic migrations via a fresh autogenerate baseline, then this
script against local PostgreSQL 16.8): 16 routes, DEMO_GENERATOR data
source, default admin user, 7330 fare observations (~95% VALID), airlines
derived from observed data, and an active index config. See
tests/test_db_schema.py::build_seeded_db for the closest offline
verification (SQLite translation of the schema with real generated data).
"""

import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.database import SessionLocal, engine
from app.core.json_safe import records_json_safe
from app.core.security import hash_password
from app.models import Base, Route, DataSource, User, IndexConfigModel, Airline
from app.services.demo_data_generator import ROUTE_BASKET, generate_demo_observations
from app.services.data_processing import run_pipeline
from app.models.observations import FareObservation
from app.services.index_engine import METHODOLOGY_VERSION


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Route).count() == 0:
            for route, (weight, _, tier) in ROUTE_BASKET.items():
                origin, dest = route.split("-")
                db.add(Route(origin=origin, destination=dest, weight=weight, distance_tier=tier))
            print(f"Seeded {len(ROUTE_BASKET)} routes.")

        sources_to_seed = [
            ("DEMO_GENERATOR", "DEMO_SIMULATED"),
            ("GOOGLE_FLIGHTS_API", "LIVE_SCRAPE"),
            ("GOOGLE_FLIGHTS", "LIVE_SCRAPE"),
            ("MOSPI_CPI", "PUBLIC_DATASET"),
            ("KIWI_FLIGHTS", "LIVE_SCRAPE"),
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
                    "Refusing to seed in production with a default/guardable admin "
                    "password. Set SEED_ADMIN_PASSWORD to a strong unique value."
                )
            if admin_password == admin_email.split("@")[0]:
                db.close()
                raise RuntimeError(
                    "Refusing to seed in production: SEED_ADMIN_PASSWORD must not "
                    "equal the email local part."
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

        from app.models.backtesting import ReferenceDataPoint
        from app.services.dgca_service import DGCA_HISTORICAL_BENCHMARK

        if db.query(ReferenceDataPoint).count() == 0:
            for dataset in ["DGCA_MONTHLY_AVG", "DGCA_DOMESTIC_BENCHMARK", "DEMO_REFERENCE"]:
                for period, val in DGCA_HISTORICAL_BENCHMARK.items():
                    factor = 1.0 if "DGCA" in dataset else 1.015
                    db.add(ReferenceDataPoint(
                        dataset_name=dataset,
                        period=period,
                        value=round(val * factor, 2),
                        label="ALL_INDIA_AVG",
                    ))
            db.commit()
            print("Seeded DGCA and demonstration benchmark reference datasets.")


        raw = generate_demo_observations(start_date=date(2026, 1, 1), n_months=6)
        clean_df, report = run_pipeline(raw, source="DEMO_SIMULATED", source_type="DEMO_SIMULATED")
        rows = clean_df.to_dict("records")

        if db.query(Airline).count() == 0:
            known_iata = {"IndiGo": "6E", "Air India": "AI", "Air India Express": "IX",
                          "Akasa Air": "QP", "SpiceJet": "SG", "Vistara": "UK",
                          "Go First": "G8", "Alliance Air": "9I"}
            for name in sorted(clean_df["airline"].dropna().unique()):
                db.add(Airline(name=name, iata_code=known_iata.get(name), active=True))
            db.commit()
            print(f"Seeded {db.query(Airline).count()} airlines from observed data.")

        if db.query(FareObservation).count() == 0:
            cleaned_rows = records_json_safe([
                {k: r[k] for k in r if k in FareObservation.__table__.columns.keys()}
                for r in rows
            ])
            db.bulk_insert_mappings(FareObservation, cleaned_rows)
            db.commit()
            print(f"Seeded {len(rows)} fare observations ({report.as_dict()}).")
        else:
            print(f"fare_observations already populated ({db.query(FareObservation).count()} rows); skipping observation seed.")

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
