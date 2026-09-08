"""Reference/configuration data — everything an ADMIN can edit without a
code change, per spec section 4 ("Store routes, route weights, carriers
and other index configuration in the database") and section 10."""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    weight = Column(Float, nullable=False)
    distance_tier = Column(String(20), nullable=True)  # trunk / regional
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("origin", "destination", name="uq_route_pair"),)

    @property
    def route_key(self) -> str:
        return f"{self.origin}-{self.destination}"


class Airline(Base):
    __tablename__ = "airlines"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    iata_code = Column(String(2), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)   # e.g. "INDIGO_WEB", "DEMO_GENERATOR"
    source_type = Column(String(30), nullable=False)  # LIVE_SCRAPE / PUBLIC_DATASET / DEMO_SIMULATED
    base_url = Column(String(255), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    min_delay_seconds = Column(Float, default=5.0)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class BookingWindowConfig(Base):
    """Configurable T+n booking windows tracked by the platform
    (spec section 4: "Support booking windows such as T+1, T+7, T+15,
    T+30 and T+45")."""
    __tablename__ = "booking_window_configs"

    id = Column(Integer, primary_key=True)
    days = Column(Integer, nullable=False, unique=True)
    weight = Column(Float, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
