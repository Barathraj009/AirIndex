"""Index configuration + computed index run history. `IndexRun` rows are
the persisted output of index_engine.compute_index(); storing the full
breakdown means the "Airfare Price Index" and "Methodology" dashboard
pages can render historical calculations without recomputing them, while
still being fully reproducible from raw data if needed (spec section 5)."""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class IndexConfigModel(Base):
    __tablename__ = "index_configs"

    id = Column(Integer, primary_key=True)
    base_period = Column(String(7), nullable=False)  # "YYYY-MM"
    methodology_version = Column(String(30), nullable=False)
    booking_window_weights = Column(JSON, nullable=True)  # {"T+1": 0.3, ...}
    include_suspicious = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    notes = Column(Text, nullable=True)


class IndexRun(Base):
    __tablename__ = "index_runs"

    id = Column(Integer, primary_key=True)
    index_config_id = Column(Integer, ForeignKey("index_configs.id"), nullable=False)

    as_of_period = Column(String(7), nullable=False, index=True)
    index_value = Column(Float, nullable=False)
    change_from_base_pct = Column(Float, nullable=False)
    n_observations_used = Column(Integer, default=0)
    routes_missing_data = Column(JSON, nullable=True)  # list[str]
    calculation_breakdown = Column(JSON, nullable=True)  # list[str], the transparency trace

    computed_at = Column(DateTime(timezone=True), default=_utcnow)


class RouteContribution(Base):
    __tablename__ = "index_route_contributions"

    id = Column(Integer, primary_key=True)
    index_run_id = Column(Integer, ForeignKey("index_runs.id"), nullable=False, index=True)
    route = Column(String(10), nullable=False)  # "DEL-BOM"
    weight = Column(Float, nullable=False)
    base_period_fare = Column(Float, nullable=True)
    as_of_period_fare = Column(Float, nullable=True)
    relative = Column(Float, nullable=True)
    contribution_pct = Column(Float, nullable=False)


class AirlineContribution(Base):
    __tablename__ = "index_airline_contributions"

    id = Column(Integer, primary_key=True)
    index_run_id = Column(Integer, ForeignKey("index_runs.id"), nullable=False, index=True)
    airline = Column(String(100), nullable=False)
    contribution_pct = Column(Float, nullable=False)
