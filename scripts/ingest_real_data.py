#!/usr/bin/env python3
"""
AirIndex India — Real Data Ingestion Script
=============================================
Fetches CPI airfare data from MoSPI (esankhyiki.mospi.gov.in) and
populates the database. Replaces the demo seed_database.py for
production/real-data deployments.

Usage:
    python scripts/ingest_real_data.py

Requires:
    - DATABASE_URL environment variable (PostgreSQL connection string)
    - Network access to api.mospi.gov.in
    - All backend dependencies installed (pip install -r backend/requirements.txt)
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# --- Import project modules ---
from app.models.base import Base
from app.models.reference import Route, DataSource
from app.models.index import IndexConfigModel
from app.models.observations import FareObservation
from app.models.ingestion import IngestionRun
from app.services.data_processing import run_pipeline

# Import the real MoSPI adapter
from ingestion.adapters.mospi_adapter import MospiCpiAdapter
from ingestion.adapters.base import CollectionRequest


def get_db_session() -> Session:
    """Create a database session from DATABASE_URL."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        print("Example: export DATABASE_URL=postgresql://user:pass@localhost:5432/airindex")
        sys.exit(1)

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def ensure_routes(db: Session) -> None:
    """Ensure the standard route basket exists in the database."""
    routes_data = [
        ("DEL", "BOM", 0.13), ("DEL", "BLR", 0.11), ("BOM", "BLR", 0.09),
        ("DEL", "CCU", 0.08), ("DEL", "HYD", 0.09), ("BLR", "HYD", 0.07),
        ("DEL", "MAA", 0.08), ("BOM", "MAA", 0.07), ("DEL", "GOI", 0.05),
        ("BOM", "GOI", 0.04), ("BLR", "CCU", 0.04), ("DEL", "TRV", 0.04),
        ("BOM", "HYD", 0.03), ("DEL", "PNQ", 0.02), ("BLR", "MAA", 0.02),
        ("BOM", "CCU", 0.02),
    ]

    existing = {r.route_key for r in db.query(Route).all()}
    added = 0
    for origin, dest, weight in routes_data:
        route_key = f"{origin}-{dest}"
        if route_key not in existing:
            db.add(Route(origin=origin, destination=dest, weight=weight, active=True))
            added += 1

    if added:
        db.commit()
        print(f"  Added {added} routes to database")


def ensure_data_source(db: Session) -> DataSource:
    """Ensure MOSPI_CPI data source exists."""
    source = db.query(DataSource).filter(DataSource.name == "MOSPI_CPI").first()
    if not source:
        source = DataSource(
            name="MOSPI_CPI",
            source_type="PUBLIC_DATASET",
            active=True,
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        print("  Created MOSPI_CPI data source")
    return source


def ensure_index_config(db: Session) -> None:
    """Ensure an active index configuration exists."""
    active = db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first()  # noqa: E712
    if not active:
        config = IndexConfigModel(
            base_period="2026-01",
            methodology_version="APIx-v1.0.0",
            include_suspicious=False,
            is_active=True,
            created_by="ingest_real_data.py",
            notes="Auto-created by real data ingestion script",
        )
        db.add(config)
        db.commit()
        print("  Created default index configuration (base_period=2026-01)")


def ingest_mospi_data(db: Session) -> None:
    """Fetch real MoSPI CPI data and load into database."""
    source = ensure_data_source(db)

    print("\nFetching CPI transport data from MoSPI API...")
    print("  Source: https://esankhyiki.mospi.gov.in")
    print("  API: https://api.mospi.gov.in/api/cpi/getCPIData")
    print("  Target: Code 07.3.3.1 = Passenger transport by air, domestic")

    adapter = MospiCpiAdapter()
    request = CollectionRequest(
        routes=[r.route_key for r in db.query(Route).filter(Route.active == True).all()],  # noqa: E712
        booking_windows=[30],
        as_of=date.today(),
    )

    raw_df, err = adapter.run(request)
    if raw_df is None:
        print(f"\n  FAILED: {err}")
        print("  Falling back to demo data generator...")
        return False

    print(f"  Collected {len(raw_df)} raw observations")

    # Run through data processing pipeline
    clean_df, report = run_pipeline(raw_df, source="MOSPI_CPI", source_type="PUBLIC_DATASET")
    print(f"  Pipeline: {report.valid} valid, {report.suspicious} suspicious, "
          f"{report.invalid} invalid, {report.unavailable} unavailable")

    # Create ingestion run record
    run = IngestionRun(
        data_source_id=source.id,
        triggered_by="ingest_real_data.py",
        status="SUCCESS",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        rows_collected=len(clean_df),
        rows_valid=report.valid,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Insert observations (idempotent — skip duplicates)
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.core.json_safe import records_json_safe

    rows = clean_df.to_dict("records")
    payload = records_json_safe([
        {**{k: r[k] for k in r if k in FareObservation.__table__.columns.keys()},
         "ingestion_run_id": run.id}
        for r in rows
    ])
    inserted = db.execute(
        pg_insert(FareObservation).values(payload)
        .on_conflict_do_nothing(index_elements=[FareObservation.__table__.c.observation_id])
    ).rowcount

    source.last_success_at = datetime.now(timezone.utc)
    db.commit()

    print(f"\n  SUCCESS: Inserted {inserted} new observations from MoSPI CPI data")
    print(f"  Data source: PUBLIC_DATASET (esankhyiki.mospi.gov.in)")
    print(f"  CPI code: 07.3.3.1 = Passenger transport by air, domestic")
    return True


def main():
    print("=" * 60)
    print("AirIndex India — Real Data Ingestion")
    print("Source: MoSPI CPI via esankhyiki.mospi.gov.in")
    print("=" * 60)

    db = get_db_session()

    try:
        print("\n1. Setting up routes...")
        ensure_routes(db)

        print("\n2. Setting up index configuration...")
        ensure_index_config(db)

        print("\n3. Ingesting real MoSPI CPI data...")
        success = ingest_mospi_data(db)

        if success:
            # Count observations
            count = db.query(FareObservation).filter(
                FareObservation.source == "MOSPI_CPI"
            ).count()
            print(f"\n4. Total MoSPI observations in database: {count}")

            # Show date range
            result = db.execute(text(
                "SELECT MIN(travel_date), MAX(travel_date) FROM fare_observations "
                "WHERE source = 'MOSPI_CPI'"
            )).fetchone()
            if result:
                print(f"   Date range: {result[0]} to {result[1]}")
        else:
            print("\n4. MoSPI fetch failed. Run scripts/seed_database.py for demo data instead.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
