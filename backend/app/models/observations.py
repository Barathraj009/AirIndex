"""Fare observations — one row per (route, airline, flight, travel_date,
collection_timestamp) fare quote, raw and normalized never mixed: this
table stores the *normalized* output of data_processing.run_pipeline().
Raw payloads are kept separately (see IngestionRun.raw_payload_path) per
spec section 3: "Store raw collected information separately from
cleaned/normalized data."

Column set intentionally matches
backend/app/services/data_processing.CANONICAL_COLUMNS exactly, so the
already-tested pipeline's output DataFrame can be bulk-inserted with a
straightforward column mapping and no translation layer to keep in sync.
"""

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.models.base import Base


class FareObservation(Base):
    __tablename__ = "fare_observations"

    id = Column(Integer, primary_key=True)
    observation_id = Column(String(16), nullable=False, unique=True, index=True)  # dedup hash

    origin = Column(String(3), nullable=False, index=True)
    destination = Column(String(3), nullable=False, index=True)
    airline = Column(String(100), nullable=False, index=True)
    flight_number = Column(String(20), nullable=True)

    travel_date = Column(Date, nullable=False, index=True)
    collection_timestamp = Column(DateTime(timezone=True), nullable=False)
    booking_window_days = Column(Integer, nullable=True, index=True)

    fare_class = Column(String(30), nullable=True)
    base_fare = Column(Float, nullable=True)
    taxes_fees = Column(Float, nullable=True)
    total_fare = Column(Float, nullable=True)
    currency = Column(String(3), default="INR")

    availability_status = Column(String(20), default="UNKNOWN")

    source = Column(String(100), nullable=False)
    source_type = Column(String(30), nullable=False, index=True)

    data_quality_status = Column(String(20), nullable=False, index=True)
    quality_flags = Column(String(500), nullable=True)

    ingestion_run_id = Column(Integer, ForeignKey("ingestion_runs.id"), nullable=True)

    __table_args__ = (
        Index("ix_route_period", "origin", "destination", "travel_date"),
        Index("ix_route_window_period", "origin", "destination", "booking_window_days", "travel_date"),
        Index("ix_obs_window_quality", "booking_window_days", "data_quality_status"),
        Index("ix_obs_airline_date", "airline", "travel_date"),
    )

