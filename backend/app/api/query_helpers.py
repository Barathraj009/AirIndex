"""Bridges the SQLAlchemy DB layer and the framework-agnostic,
already-tested service layer (backend/app/services/*.py): loads
FareObservation rows into a pandas DataFrame with exactly the columns
index_engine.compute_index / data_processing functions expect, so the
same tested logic that ran against the demo CSV in Phase 1 runs
unchanged against real database rows here."""

import pandas as pd
from sqlalchemy.orm import Session

from app.models.observations import FareObservation


def load_observations_df(db: Session, origin: str = None, destination: str = None,
                          period: str = None) -> pd.DataFrame:
    q = db.query(FareObservation)
    if origin:
        q = q.filter(FareObservation.origin == origin)
    if destination:
        q = q.filter(FareObservation.destination == destination)
    rows = [
        {
            "origin": r.origin, "destination": r.destination, "airline": r.airline,
            "flight_number": r.flight_number, "travel_date": r.travel_date.isoformat(),
            "collection_timestamp": r.collection_timestamp.isoformat(),
            "booking_window_days": r.booking_window_days, "fare_class": r.fare_class,
            "base_fare": r.base_fare, "taxes_fees": r.taxes_fees, "total_fare": r.total_fare,
            "currency": r.currency, "availability_status": r.availability_status,
            "source": r.source, "source_type": r.source_type,
            "data_quality_status": r.data_quality_status, "quality_flags": r.quality_flags,
        }
        for r in q.all()
    ]
    df = pd.DataFrame(rows)
    if period and not df.empty:
        df = df[df["travel_date"].str.startswith(period)]
    return df
