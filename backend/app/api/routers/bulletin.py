from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.api.query_helpers import load_observations_df
from app.services.index_engine import compute_index, compute_index_series
from app.services.anomaly_detector import detect_fare_anomalies
from app.services.forecaster import forecast_index_series
from app.api.routers.index import _active_config_and_weights

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/monthly-bulletin")
def get_monthly_bulletin(db: Session = Depends(get_db), _=Depends(require_permission("view_dashboard"))):
    """
    Generates an official MoSPI/DGCA Statistical Monthly Airfare Bulletin
    containing index values, MoM/YoY growth, anomaly alerts, and forward forecast.
    """
    config, _active = _active_config_and_weights(db)
    df = load_observations_df(db)

    periods = sorted(df["travel_date"].str[:7].unique().tolist()) if not df.empty else []
    current_period = periods[-1] if periods else "2026-06"

    current_index = compute_index(df, config, as_of_period=current_period)
    trend_series = compute_index_series(df, config, periods) if periods else []

    anomalies = detect_fare_anomalies(df)
    forecast = forecast_index_series(trend_series, forecast_steps=3) if trend_series else {}

    top_contributors = sorted(
        current_index.route_contributions.items(),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:5]

    return {
        "title": f"AirIndex India Monthly Statistical Bulletin — {current_period}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": config.methodology_version,
        "base_period": config.base_period,
        "current_period": current_period,
        "executive_summary": {
            "current_apix_value": round(current_index.index_value, 2),
            "change_from_base_pct": round(current_index.change_from_base_pct, 2),
            "total_observations_analyzed": current_index.n_observations_used,
            "routes_evaluated": len(current_index.route_fares),
            "active_price_anomalies_detected": len(anomalies),
            "projected_forward_quarter_growth_pct": forecast.get("projected_horizon_growth_pct"),
        },
        "top_route_contributors": [
            {"route": r, "contribution_points": round(contrib, 3)}
            for r, contrib in top_contributors
        ],
        "airline_proxy_contributions": current_index.airline_contributions,
        "recent_trend": trend_series[-6:] if len(trend_series) >= 6 else trend_series,
        "forward_forecast": forecast.get("forecast_points", []),
        "priority_anomalies": anomalies[:5],
    }
