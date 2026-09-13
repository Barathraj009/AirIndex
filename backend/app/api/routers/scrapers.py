"""Scraper Monitor API — Phase 14 of the web-scraping spec.

Endpoints:
  GET /api/scrapers                 -> registry metadata + status for all 11
                                       web sources (no network)
  GET /api/scrapers/status          -> status detail incl. per-source last run;
                                       ?force_robots_check=1 triggers a live
                                       fail-closed robots.txt re-check (cached
                                       responses fetched, cache bypassed)
  GET /api/scrapers/runs            -> recent scraper run history (ingestion_runs
                                       scoped to the web-scraper source names)
"""

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.models import IngestionRun

_REPO_ROOT = str(Path(__file__).resolve().parents[4])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

router = APIRouter(prefix="/api/scrapers", tags=["scraping"])


def _web_source_names() -> list[str]:
    from ingestion.scrapers.sources import SOURCE_REGISTRY
    return [s.source_name for s in SOURCE_REGISTRY]


@router.get("")
@router.get("/")
def list_scrapers(db: Session = Depends(get_db),
                  _=Depends(require_permission("view_scraping_monitor"))):
    from app.services.scraper_status import build_status_summary
    from ingestion.scrapers.sources import SOURCE_REGISTRY

    return build_status_summary(list(SOURCE_REGISTRY), db, include_robot_checks=False)


@router.get("/status")
def scraper_status(db: Session = Depends(get_db),
                   force_robots_check: bool = Query(default=False),
                   _=Depends(require_permission("view_scraping_monitor"))):
    from app.services.scraper_status import build_status_summary
    from ingestion.scrapers.sources import SOURCE_REGISTRY

    return build_status_summary(
        list(SOURCE_REGISTRY), db,
        include_robot_checks=True,
        force_robot_checks=force_robots_check,
    )


@router.get("/runs")
def scraper_runs(limit: int = Query(default=50, le=500), db: Session = Depends(get_db),
                 _=Depends(require_permission("view_scraping_monitor"))):
    from app.models.reference import DataSource

    web_names = _web_source_names()
    source_ids = [r.id for r in db.query(DataSource).filter(DataSource.name.in_(web_names)).all()]
    q = db.query(IngestionRun)
    if source_ids:
        q = q.filter(IngestionRun.data_source_id.in_(source_ids))
    else:
        q = q.filter(IngestionRun.id == -1)
    rows = q.order_by(IngestionRun.started_at.desc()).limit(limit).all()
    names_by_id = {d.id: d.name for d in db.query(DataSource).all()}
    return [
        {
            "id": r.id,
            "source_name": names_by_id.get(r.data_source_id, r.data_source_id),
            "status": r.status,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "rows_collected": r.rows_collected,
            "rows_valid": r.rows_valid,
            "error_message": r.error_message,
        }
        for r in rows
    ]