from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.models.observations import FareObservation
from app.schemas.reference import FareObservationOut, DataQualitySummaryOut

router = APIRouter(prefix="/api", tags=["fares"])


@router.get("/fares", response_model=list[FareObservationOut])
def list_fares(
    origin: str | None = None,
    destination: str | None = None,
    airline: str | None = None,
    booking_window_days: int | None = None,
    data_quality_status: str | None = None,
    limit: int = Query(default=200, le=2000),
    offset: int = 0,
    db: Session = Depends(get_db),
    _=Depends(require_permission("view_dashboard")),
):
    """Backs the Data Explorer page: filterable, paginated raw
    observation listing."""
    q = db.query(FareObservation)
    if origin:
        q = q.filter(FareObservation.origin == origin)
    if destination:
        q = q.filter(FareObservation.destination == destination)
    if airline:
        q = q.filter(FareObservation.airline == airline)
    if booking_window_days is not None:
        q = q.filter(FareObservation.booking_window_days == booking_window_days)
    if data_quality_status:
        q = q.filter(FareObservation.data_quality_status == data_quality_status)
    return q.offset(offset).limit(limit).all()


@router.get("/data-quality/summary", response_model=DataQualitySummaryOut)
def data_quality_summary(db: Session = Depends(get_db), _=Depends(require_permission("view_data_quality"))):
    from app.api.query_helpers import load_observations_df
    from app.services.data_processing import QualityReport, DataQualityStatus

    df = load_observations_df(db)
    report = QualityReport()
    report.total_rows = len(df)
    if not df.empty:
        counts = df["data_quality_status"].value_counts().to_dict()
        report.valid = counts.get(DataQualityStatus.VALID.value, 0)
        report.suspicious = counts.get(DataQualityStatus.SUSPICIOUS.value, 0)
        report.invalid = counts.get(DataQualityStatus.INVALID.value, 0)
        report.unavailable = counts.get(DataQualityStatus.UNAVAILABLE.value, 0)
        report.issues = df.loc[df["quality_flags"].notna() & (df["quality_flags"] != ""),
                                "quality_flags"].value_counts().index.tolist()
    return report.as_dict()
