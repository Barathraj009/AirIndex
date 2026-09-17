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


@router.get("/fares/latest")
def latest_fares(origin: str | None = None,
                 destination: str | None = None,
                 from_date: str | None = None,
                 db: Session = Depends(get_db),
                 _=Depends(require_permission("view_dashboard"))):
    """Latest normalized fare per (route, airline, travel_date) — the
    freshest white-labelled observations for the scraper monitor.

    Uses VALID rows ordered by collection timestamp; returns the most
    recent snapshot so the UI can show 'as of' fares without duplicate
    historical rows.

    ``from_date`` (YYYY-MM-DD) filters to travel dates on or after that
    day, so charts like "Fares by Departure Date" can start at today.
    """
    from datetime import date
    from sqlalchemy import func

    if from_date:
        try:
            from_date_obj = date.fromisoformat(from_date)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="from_date must be YYYY-MM-DD")

    valid_statuses = ("VALID",)
    base = (
        db.query(
            FareObservation.origin.label("origin"),
            FareObservation.destination.label("destination"),
            FareObservation.airline.label("airline"),
            FareObservation.travel_date.label("travel_date"),
            func.max(FareObservation.collection_timestamp).label("latest_collected"),
        )
        .filter(FareObservation.data_quality_status.in_(valid_statuses))
        .group_by(FareObservation.origin, FareObservation.destination,
                  FareObservation.airline, FareObservation.travel_date)
    )
    if origin:
        base = base.filter(FareObservation.origin == origin)
    if destination:
        base = base.filter(FareObservation.destination == destination)
    if from_date:
        base = base.filter(FareObservation.travel_date >= from_date_obj)

    latest_snapshot = base.subquery()
    rows = (
        db.query(FareObservation)
        .join(
            latest_snapshot,
            (FareObservation.origin == latest_snapshot.c.origin)
            & (FareObservation.destination == latest_snapshot.c.destination)
            & (FareObservation.airline == latest_snapshot.c.airline)
            & (FareObservation.travel_date == latest_snapshot.c.travel_date)
            & (FareObservation.collection_timestamp == latest_snapshot.c.latest_collected),
        )
        .order_by(
            FareObservation.travel_date.asc(),
            FareObservation.collection_timestamp.desc(),
        )
        .all()
    )

    return [
        {
            "origin": r.origin,
            "destination": r.destination,
            "airline": r.airline,
            "flight_number": r.flight_number,
            "travel_date": r.travel_date,
            "total_fare": r.total_fare,
            "base_fare": r.base_fare,
            "taxes_fees": r.taxes_fees,
            "currency": r.currency,
            "booking_window_days": r.booking_window_days,
            "source": r.source,
            "source_type": r.source_type,
            "collection_timestamp": r.collection_timestamp,
        }
        for r in rows
    ]


@router.get("/fares/routes")
def route_summaries(db: Session = Depends(get_db),
                    _=Depends(require_permission("view_dashboard"))):
    """Per-route fare summary for the Dashboard route basket — count,
    valid count, median/min/max fare, and the freshest collection time."""
    from sqlalchemy import func, case

    rows = (
        db.query(
            FareObservation.origin.label("origin"),
            FareObservation.destination.label("destination"),
            func.count(FareObservation.id).label("n"),
            func.sum(case((FareObservation.data_quality_status == "VALID", 1), else_=0)).label("n_valid"),
            func.avg(FareObservation.total_fare).label("avg_fare"),
            func.min(FareObservation.total_fare).label("min_fare"),
            func.max(FareObservation.total_fare).label("max_fare"),
            func.max(FareObservation.collection_timestamp).label("latest_collected"),
        )
        .group_by(FareObservation.origin, FareObservation.destination)
        .order_by(FareObservation.origin, FareObservation.destination)
        .all()
    )

    return [
        {
            "route": f"{r.origin}-{r.destination}",
            "origin": r.origin,
            "destination": r.destination,
            "n": r.n,
            "n_valid": r.n_valid or 0,
            "avg_fare": r.avg_fare,
            "min_fare": r.min_fare,
            "max_fare": r.max_fare,
            "latest_collected": r.latest_collected,
        }
        for r in rows
    ]
