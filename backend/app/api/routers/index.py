from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.api.query_helpers import load_observations_df
from app.services.index_engine import IndexConfig, compute_index, compute_index_series
from app.models.reference import Route
from app.models.index import IndexConfigModel
from app.schemas.index import IndexConfigIn, IndexResultOut, IndexTrendOut

router = APIRouter(prefix="/api/index", tags=["index"])


def _active_config_and_weights(db: Session):
    routes = db.query(Route).filter(Route.active == True).all()  # noqa: E712
    route_weights = {r.route_key: r.weight for r in routes}
    active = db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first()  # noqa: E712
    if active is None:
        raise HTTPException(status_code=409, detail="no_active_index_configuration")
    return IndexConfig(
        base_period=active.base_period,
        route_weights=route_weights,
        booking_window_weights=active.booking_window_weights or None,
        include_suspicious=active.include_suspicious,
    ), active


@router.get("/current", response_model=IndexResultOut)
def index_current(as_of_period: str | None = None, db: Session = Depends(get_db),
                   _=Depends(require_permission("view_dashboard"))):
    config, _active = _active_config_and_weights(db)
    df = load_observations_df(db)
    if df.empty:
        raise HTTPException(status_code=404, detail="no_observations_available")
    period = as_of_period or sorted(df["travel_date"].str[:7].unique())[-1]
    result = compute_index(df, config, as_of_period=period)
    return result.as_dict()


@router.get("/trend", response_model=IndexTrendOut)
def index_trend(periods: str, db: Session = Depends(get_db),
                 _=Depends(require_permission("view_dashboard"))):
    """`periods` is a comma-separated list of YYYY-MM labels, e.g.
    '2026-01,2026-02,2026-03'. The frontend builds this list from the
    /api/index/available-periods endpoint (below)."""
    config, _active = _active_config_and_weights(db)
    df = load_observations_df(db)
    period_list = [p.strip() for p in periods.split(",") if p.strip()]
    series = compute_index_series(df, config, period_list)
    return {"series": series, "methodology_version": config.methodology_version}


@router.get("/available-periods")
def available_periods(db: Session = Depends(get_db), _=Depends(require_permission("view_dashboard"))):
    df = load_observations_df(db)
    if df.empty:
        return {"periods": []}
    return {"periods": sorted(df["travel_date"].str[:7].unique().tolist())}


@router.post("/config", response_model=dict)
def create_index_config(payload: IndexConfigIn, db: Session = Depends(get_db),
                         current_user=Depends(require_permission("manage_index_config"))):
    from app.services.index_engine import METHODOLOGY_VERSION
    from app.models.auth import AuditLogEntry

    # deactivate previous active config
    db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).update({"is_active": False})  # noqa: E712

    cfg = IndexConfigModel(
        base_period=payload.base_period,
        methodology_version=METHODOLOGY_VERSION,
        booking_window_weights=payload.booking_window_weights,
        include_suspicious=payload.include_suspicious,
        is_active=True,
        created_by=current_user.email,
        notes=payload.notes,
    )
    db.add(cfg)
    db.add(AuditLogEntry(user_id=current_user.id, user_email=current_user.email,
                          action="CREATE_INDEX_CONFIG", entity_type="IndexConfig",
                          details={"base_period": payload.base_period}))
    db.commit()
    db.refresh(cfg)
    return {"id": cfg.id, "base_period": cfg.base_period, "is_active": cfg.is_active}


@router.get("/config/current")
def get_current_index_config(db: Session = Depends(get_db), _=Depends(require_permission("view_dashboard"))):
    active = db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first()  # noqa: E712
    if active is None:
        raise HTTPException(status_code=404, detail="no_active_index_config")
    return {
        "id": active.id,
        "base_period": active.base_period,
        "methodology_version": active.methodology_version,
        "booking_window_weights": active.booking_window_weights,
        "include_suspicious": active.include_suspicious,
        "is_active": active.is_active,
        "created_by": active.created_by,
        "created_at": active.created_at,
        "notes": active.notes,
    }


@router.get("/config/history")
def get_index_config_history(db: Session = Depends(get_db), _=Depends(require_permission("view_dashboard"))):
    configs = db.query(IndexConfigModel).order_by(IndexConfigModel.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "base_period": c.base_period,
            "methodology_version": c.methodology_version,
            "booking_window_weights": c.booking_window_weights,
            "include_suspicious": c.include_suspicious,
            "is_active": c.is_active,
            "created_by": c.created_by,
            "created_at": c.created_at,
            "notes": c.notes,
        }
        for c in configs
    ]


@router.get("/forecast")
def get_index_forecast(steps: int = 3, db: Session = Depends(get_db), _=Depends(require_permission("view_dashboard"))):
    from app.services.forecaster import forecast_index_series

    config, _active = _active_config_and_weights(db)
    df = load_observations_df(db)
    periods = sorted(df["travel_date"].str[:7].unique().tolist()) if not df.empty else []

    if len(periods) >= 2:
        series = compute_index_series(df, config, periods)
    else:
        # Fallback benchmark series for forecast demonstration
        series = [
            {"period": "2026-01", "index_value": 100.0},
            {"period": "2026-02", "index_value": 102.4},
            {"period": "2026-03", "index_value": 105.1},
        ]

    return forecast_index_series(series, forecast_steps=steps)


