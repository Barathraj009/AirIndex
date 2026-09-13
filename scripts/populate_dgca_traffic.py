#!/usr/bin/env python3
"""
Populate DGCA City-Pair Traffic Table
======================================
Upserts the official DGCA domestic city-pair passenger traffic figures
(DGCA Domestic Air Transport Reports, 2025-2026) into the
dgca_route_traffic table used for route-weight calibration.

Usage:
    python scripts/populate_dgca_traffic.py

Requires:
    - DATABASE_URL environment variable
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.base import Base
from app.models.dgca import DgcaTrafficRecord
from ingestion.adapters.dgca_traffic import fetch_dgca_traffic_records, DGCA_SOURCE_URL


def main():
    print("=" * 60)
    print("AirIndex India — Populate DGCA City-Pair Traffic")
    print(f"Source: {DGCA_SOURCE_URL}")
    print("=" * 60)

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("\nERROR: DATABASE_URL not set")
        print("Example: export DATABASE_URL=postgresql://user:pass@localhost:5432/airindex")
        sys.exit(1)

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        print("\nPreparing DGCA city-pair traffic records...")
        records = fetch_dgca_traffic_records()

        if not records:
            print("ERROR: No DGCA traffic records available")
            sys.exit(1)

        print(f"  {len(records)} directional city-pair records")

        inserted = 0
        for rec in records:
            result = db.execute(
                pg_insert(DgcaTrafficRecord)
                .values(**rec)
                .on_conflict_do_nothing(index_elements=[DgcaTrafficRecord.route_key])
            )
            inserted += result.rowcount

        db.commit()

        print(f"\n  Inserted {inserted} new records")
        print(f"  Total records: {db.query(DgcaTrafficRecord).count()}")

        top = db.query(DgcaTrafficRecord).order_by(DgcaTrafficRecord.passengers.desc()).limit(3).all()
        print("\n  Top city-pairs by traffic (lakhs):")
        for r in top:
            print(f"    {r.route_key}: {r.passengers}")

    finally:
        db.close()


if __name__ == "__main__":
    main()