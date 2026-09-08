import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.models.observations import FareObservation

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/fares.csv")
def export_fares_csv(origin: str | None = None, destination: str | None = None,
                      db: Session = Depends(get_db), _=Depends(require_permission("export_data"))):
    q = db.query(FareObservation)
    if origin:
        q = q.filter(FareObservation.origin == origin)
    if destination:
        q = q.filter(FareObservation.destination == destination)

    buf = io.StringIO()
    writer = csv.writer(buf)
    columns = [c.name for c in FareObservation.__table__.columns]
    writer.writerow(columns)
    for row in q.yield_per(1000):
        writer.writerow([getattr(row, c) for c in columns])
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=airindex_fares_export.csv"},
    )
