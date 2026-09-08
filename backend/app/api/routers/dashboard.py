from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.api.query_helpers import load_observations_df
from app.services.data_processing import run_pipeline
from app.services.index_engine import IndexConfig, compute_index
from app.models.reference import Route
from app.models.index import IndexConfigModel

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), _=Depends(require_permission("view_dashboard"))):
    routes = db.query(Route).filter(Route.active == True).all()  # noqa: E712
    route_weights = {r.route_key: r.weight for r in routes}

    active_config = db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first()  # noqa: E712
    base_period = active_config.base_period if active_config else None

    df = load_observations_df(db)
    if df.empty or base_period is None:
        return {"status": "NO_DATA", "message": "No observations or active index configuration yet."}

    periods = sorted(df["travel_date"].str[:7].unique())
    current_period = periods[-1]

    config = IndexConfig(base_period=base_period, route_weights=route_weights,
                          booking_window_weights=(active_config.booking_window_weights or None))
    result = compute_index(df, config, as_of_period=current_period)

    return {
        "index": result.as_dict(),
        "n_routes_tracked": len(route_weights),
        "n_airlines_tracked": df["airline"].nunique(),
        "current_period": current_period,
        "base_period": base_period,
    }
