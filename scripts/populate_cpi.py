#!/usr/bin/env python3
"""
Populate CPI Airfare Index Table with MoSPI Data
=================================================
Fetches real CPI data from https://api.mospi.gov.in and stores it
in the cpi_airfare_index table.

Usage:
    python scripts/populate_cpi.py

Requires:
    - DATABASE_URL environment variable
    - Network access to api.mospi.gov.in
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
from app.models.cpi import CpiAirfareIndex
from ingestion.adapters.mospi_cpi import fetch_mospi_airfare_index


def main():
    print("=" * 60)
    print("AirIndex India — Populate CPI Airfare Index from MoSPI")
    print("Source: https://esankhyiki.mospi.gov.in")
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
        print("\nFetching CPI airfare data from MoSPI API...")
        records = fetch_mospi_airfare_index()

        if not records:
            print("ERROR: No data returned from MoSPI API")
            sys.exit(1)

        print(f"  Fetched {len(records)} months of data")

        # Insert (skip duplicates)
        inserted = 0
        for rec in records:
            result = db.execute(
                pg_insert(CpiAirfareIndex)
                .values(**rec)
                .on_conflict_do_nothing(index_elements=[CpiAirfareIndex.period])
            )
            inserted += result.rowcount

        db.commit()

        print(f"\n  Inserted {inserted} new records")
        print(f"  Total records: {db.query(CpiAirfareIndex).count()}")

        # Show summary
        latest = db.query(CpiAirfareIndex).order_by(CpiAirfareIndex.period.desc()).first()
        if latest:
            print(f"\n  Latest: {latest.period}")
            print(f"    Airfare CPI: {latest.airfare_index}")
            print(f"    Transport CPI: {latest.transport_index}")
            print(f"    General CPI: {latest.general_index}")
            print(f"    Inflation YoY: {latest.inflation_yoy}%")

    finally:
        db.close()


if __name__ == "__main__":
    main()
