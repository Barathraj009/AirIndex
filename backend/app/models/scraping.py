"""Scraper-specific models (Phase 12 of the web-scraping spec).

Mapping to the existing schema (documented in docs/data-schema.md):
  sources       -> data_sources            (existing reference table)
  scraper_runs  -> ingestion_runs          (existing run-tracking table)
  fare_results  -> fare_observations       (existing normalized table)

Truly-new tables added here:
  scraper_errors   -> per-source error log (robots verdicts, edge blocks,
                      parse failures) so the Scraper Monitor can show WHY
                      a source is reporting UNAVAILABLE over time.
  fare_searches    -> audit of each fare search request+response (params,
                      result count, latency) for testing and monitoring.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey

from app.models.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ScraperError(Base):
    __tablename__ = "scraper_errors"

    id = Column(Integer, primary_key=True)
    source_name = Column(String(100), nullable=False, index=True)
    error_type = Column(String(50), nullable=False)  # ROBOTS_DISALLOWED / EDGE_BLOCK / NETWORK / PARSE / UNEXPECTED
    message = Column(Text, nullable=False)
    occurred_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    scraper_run_id = Column(Integer, ForeignKey("ingestion_runs.id"), nullable=True)

    @classmethod
    def record(cls, db, *, source_name: str, error_type: str, message: str, scraper_run_id=None) -> "ScraperError":
        row = cls(
            source_name=source_name,
            error_type=error_type,
            message=message,
            scraper_run_id=scraper_run_id,
        )
        db.add(row)
        return row


class FareSearch(Base):
    __tablename__ = "fare_searches"

    id = Column(Integer, primary_key=True)
    source_name = Column(String(100), nullable=False, index=True)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    travel_date = Column(String(10), nullable=True)  # ISO date (may be a window end)
    booking_window_days = Column(Integer, nullable=True)
    request_params = Column(Text, nullable=True)  # JSON snapshot of the search request
    status = Column(String(20), nullable=False, default="ATTEMPTED")  # ATTEMPTED / SUCCESS / SOURCE_UNAVAILABLE / FAILED
    rows_returned = Column(Integer, default=0)
    latency_ms = Column(Float, nullable=True)
    searched_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    error_message = Column(Text, nullable=True)