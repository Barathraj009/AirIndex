from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.api.query_helpers import load_observations_df
from app.models.reference import Route
from app.models.index import IndexConfigModel
from app.models.backtesting import ReferenceDataPoint
from app.services.index_engine import IndexConfig, compute_index_series
from app.services.backtesting import run_backtest
from app.schemas.reference import BacktestRequest, BacktestResultOut

router = APIRouter(prefix="/api/backtesting", tags=["backtesting"])


@router.post("/run", response_model=BacktestResultOut)
def run(payload: BacktestRequest, db: Session = Depends(get_db),
        _=Depends(require_permission("run_backtesting"))):
    routes = db.query(Route).filter(Route.active == True).all()  # noqa: E712
    route_weights = {r.route_key: r.weight for r in routes}
    active_config = db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first()  # noqa: E712

    config = IndexConfig(
        base_period=active_config.base_period if active_config else payload.start_period,
        route_weights=route_weights,
    )

    df = load_observations_df(db)
    all_periods = sorted(df["travel_date"].str[:7].unique().tolist()) if not df.empty else []
    period_range = [p for p in all_periods if payload.start_period <= p <= payload.end_period]

    actual_series_raw = compute_index_series(df, config, period_range)
    actual_series = {p["period"]: p["index_value"] for p in actual_series_raw}

    ref_points = db.query(ReferenceDataPoint).filter(
        ReferenceDataPoint.dataset_name == payload.reference_dataset,
        ReferenceDataPoint.period.between(payload.start_period, payload.end_period),
    ).all()
    reference_series = {p.period: p.value for p in ref_points}

    result = run_backtest(actual_series, reference_series)
    return {
        "start_period": payload.start_period,
        "end_period": payload.end_period,
        "reference_dataset": payload.reference_dataset,
        **result,
    }


@router.get("/reference-datasets")
def list_reference_datasets(db: Session = Depends(get_db), _=Depends(require_permission("run_backtesting"))):
    """Lists which reference datasets actually have data loaded, so the
    frontend never offers a comparison that will silently come back
    empty. Per spec section 8, DGCA data must be real if selected;
    DEMO_REFERENCE is explicitly labelled as such."""
    rows = db.query(ReferenceDataPoint.dataset_name).distinct().all()
    return {"available_datasets": [r[0] for r in rows]}
