import sys
import traceback
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.models.ingestion import IngestionRun
from app.schemas.reference import IngestionRunOut, TriggerIngestionRequest
from app.services.ingestion_runner import collect_from_sources

# The `ingestion` package lives at the repo root, not under backend/app/;
# ensure it resolves regardless of the CWD uvicorn is started from.
_REPO_ROOT = str(Path(__file__).resolve().parents[4])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

router = APIRouter(prefix="/api/scraping", tags=["scraping"])


@router.get("/runs", response_model=list[IngestionRunOut])
def list_runs(limit: int = 50, db: Session = Depends(get_db),
              _=Depends(require_permission("view_scraping_monitor"))):
    return db.query(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit).all()


@router.post("/trigger")
def trigger_ingestion(payload: TriggerIngestionRequest, db: Session = Depends(get_db),
                       current_user=Depends(require_permission("trigger_ingestion"))):
    """Manually trigger a collection run. Uses the same adapter
    orchestration the scheduler (APScheduler, Phase 4) uses: each source's
    `.run()` either returns data or degrades to SOURCE UNAVAILABLE — never
    raises — so one bad source can't crash the request (spec section 12)."""
    try:
        results = collect_from_sources(
            db, source_names=payload.source_names or None,
            triggered_by=current_user.email, run_action="TRIGGER_INGESTION",
        )
    except Exception as e:  # noqa: BLE001 - surface real error for debugging
        raise HTTPException(status_code=500, detail=f"ingestion_orchestration_error: {type(e).__name__}: {e}")
    if not results:
        raise HTTPException(status_code=404, detail="no_matching_active_sources")
    return {"runs": results}
