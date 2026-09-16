"""Bridges the SQLAlchemy DB layer and the framework-agnostic,
already-tested service layer (backend/app/services/*.py): loads
FareObservation rows into a pandas DataFrame with exactly the columns
index_engine.compute_index / data_processing functions expect, so the
same tested logic that ran against the demo CSV in Phase 1 runs
unchanged against real database rows here.

The basket weights stored on Route (summing to 1.0 across the full
ROUTE_BASKET) must be renormalized whenever routes are deactivated,
because index_engine's IndexConfig validation requires the configured
weights to sum to ~1.0. active_route_weights() returns the active
routes with their weights redistributed proportionally so the index
stays valid for any active-route subset.
"""

import pandas as pd
from sqlalchemy.orm import Session

from app.models.observations import FareObservation
from app.models.reference import Route


def active_route_weights(db: Session) -> dict:
    """Return {route_key: normalized_weight} for all active routes, scaled
    to sum to ~1.0 even when only a subset of the basket is active."""
    rows = db.query(Route).filter(Route.active == True).all()  # noqa: E712
    weights = {r.route_key: r.weight for r in rows}
    total = sum(weights.values())
    if total > 0:
        weights = {k: w / total for k, w in weights.items()}
    return weights


def load_observations_df(db: Session, origin: str = None, destination: str = None,
                          period: str = None, include_benchmarks: bool = False) -> pd.DataFrame:
    """Load FareObservation rows into a pandas DataFrame.

    Benchmark/reference rows (e.g. MoSPI CPI fuel/fare benchmarks) are
    excluded by default so the airfare index and analytics are computed
    strictly from actual airfare observations. Raw fare queries (Data
    Explorer, exports) read the model directly and keep every row.
    """
    q = db.query(FareObservation)
    if not include_benchmarks:
        q = q.filter(FareObservation.fare_class != "CPI_BENCHMARK")
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
