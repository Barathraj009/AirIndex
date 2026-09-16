"""Real-data source status — replaces the old multimedia scraper monitor.

The product now serves exactly two real data sources:

* ``GOOGLE_FLIGHTS_API`` — licensed Google Flights fares via RapidAPI
  (gds_adapter); the live component of APIx.
* ``MOSPI_CPI`` — the official MoSPI CPI airfare index (07.3.3.1, 2024=100),
  used to anchor the official history and re-anchored by the scheduler.

Status is derived entirely from the database (no network calls), so this is
safe to poll and never blocks on a slow upstream.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.ingestion import IngestionRun
from app.models.reference import DataSource
from app.services.source_status import build_sources_status

router = APIRouter(prefix="/api/sources", tags=["sources"])

_SOURCE_NAMES = ("GOOGLE_FLIGHTS_API", "MOSPI_CPI")


@router.get("")
@router.get("/")
def list_sources(db: Session = Depends(get_db),
                 _=Depends(require_permission("view_scraping_monitor"))):
    return build_sources_status(db)


@router.get("/runs")
def list_runs(limit: int = Query(default=50, ge=1, le=500),
              db: Session = Depends(get_db),
              _=Depends(require_permission("view_scraping_monitor"))):
    """Recent ingestion runs for the two product sources (the history the OLD
    /api/scrapers/runs + /api/scraping/runs monitor surfaced for the 11
    scrapers; now scoped to the only two real sources)."""
    ids = [
        d.id for d in db.query(DataSource)
        .filter(DataSource.name.in_(_SOURCE_NAMES)).all()
    ]
    q = db.query(IngestionRun)
    if ids:
        q = q.filter(IngestionRun.data_source_id.in_(ids))
    else:
        q = q.filter(IngestionRun.id == -1)
    rows = q.order_by(IngestionRun.started_at.desc()).limit(limit).all()
    names = {d.id: d.name for d in db.query(DataSource).all()}
    return [
        {
            "id": r.id,
            "source_name": names.get(r.data_source_id, r.data_source_id),
            "status": r.status,
            "started_at": _iso(r.started_at),
            "completed_at": _iso(r.completed_at),
            "rows_collected": r.rows_collected,
            "rows_valid": r.rows_valid,
            "rows_invalid": r.rows_invalid,
            "rows_suspicious": r.rows_suspicious,
            "rows_unavailable": r.rows_unavailable,
            "error_message": r.error_message,
        }
        for r in rows
    ]


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None
