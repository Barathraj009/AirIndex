"""Ingestion run tracking — backs the "Scraping/Collection Monitor" page
(spec section 6) so admins can see which sources succeeded/failed and
why, per run (spec section 10: "inspect collection failures and
data-quality problems")."""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(Integer, primary_key=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    triggered_by = Column(String(100), nullable=True)  # "scheduler" or a user email for manual triggers

    started_at = Column(DateTime(timezone=True), default=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(20), default="RUNNING")  # RUNNING / SUCCESS / SOURCE_UNAVAILABLE / FAILED
    rows_collected = Column(Integer, default=0)
    rows_valid = Column(Integer, default=0)
    rows_invalid = Column(Integer, default=0)
    rows_suspicious = Column(Integer, default=0)
    rows_unavailable = Column(Integer, default=0)

    error_message = Column(Text, nullable=True)
    raw_payload_path = Column(String(255), nullable=True)  # where the raw (pre-normalization) data was archived
