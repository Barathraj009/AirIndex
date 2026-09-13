"""
DGCA Domestic Route Traffic — stores the official Directorate General of
Civil Aviation (DGCA) city-pair passenger volumes used to calibrate route
basket weights.

Each row is one directional city-pair (origin -> destination) with the
published passenger volume in lakhs for a traffic period, plus source
metadata. Uniqueness is enforced on the directional route key so admin
refreshes are idempotent.

Source: DGCA Domestic Air Transport Reports / Monthly Statistics.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime

from app.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class DgcaTrafficRecord(Base):
    """Official DGCA directional city-pair passenger traffic volume."""
    __tablename__ = "dgca_route_traffic"

    id = Column(Integer, primary_key=True)

    origin = Column(String(3), nullable=False)       # e.g. "DEL"
    destination = Column(String(3), nullable=False)  # e.g. "BOM"
    route_key = Column(String(7), nullable=False, unique=True, index=True)  # e.g. "DEL-BOM"
    passengers = Column(Float, nullable=False)       # Published volume in lakhs
    period = Column(String(20), nullable=False)      # e.g. "FY2025-26"

    source = Column(String(50), nullable=True)       # e.g. "DGCA"
    source_url = Column(String(255), nullable=True)

    # Audit
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<DgcaTrafficRecord {self.route_key}: {self.passengers} lakhs ({self.period})>"