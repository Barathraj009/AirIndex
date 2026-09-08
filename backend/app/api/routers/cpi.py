from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.api.query_helpers import load_observations_df
from app.services.index_engine import compute_index_series
from app.services.cpi_engine import (
    HISTORICAL_MOSPI_CPI,
    DEFAULT_AIRFARE_IN_CPI_WEIGHT,
    DEFAULT_TRANSPORT_WEIGHT,
    simulate_cpi_augmentation,
)
from app.api.routers.index import _active_config_and_weights

router = APIRouter(prefix="/api/cpi", tags=["cpi"])


class CpiSimulationRequest(BaseModel):
    airfare_weight_in_cpi: float = DEFAULT_AIRFARE_IN_CPI_WEIGHT
    transport_group_weight: float = DEFAULT_TRANSPORT_WEIGHT


@router.get("/baseline")
def get_cpi_baseline(_=Depends(require_permission("view_dashboard"))):
    points = [
        {
            "period": period,
            "general_cpi": data["general_cpi"],
            "transport_cpi": data["transport_cpi"],
            "airfare_subindex_lagged": data["airfare_subindex_lagged"],
        }
        for period, data in sorted(HISTORICAL_MOSPI_CPI.items())
    ]
    return {
        "base_year": "2012=100",
        "default_transport_weight_pct": DEFAULT_TRANSPORT_WEIGHT * 100,
        "default_airfare_weight_pct": DEFAULT_AIRFARE_IN_CPI_WEIGHT * 100,
        "series": points,
    }


@router.post("/simulate")
def simulate_cpi(
    payload: CpiSimulationRequest | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("view_dashboard")),
):
    req = payload or CpiSimulationRequest()
    config, active = _active_config_and_weights(db)
    df = load_observations_df(db)

    periods = sorted(df["travel_date"].str[:7].unique().tolist()) if not df.empty else []
    apix_series_dict = {}

    if periods:
        computed = compute_index_series(df, config, periods)
        for pt in computed:
            if pt["index_value"] is not None:
                apix_series_dict[pt["period"]] = pt["index_value"]

    # Fallback to simulated trajectory if no periods
    if not apix_series_dict:
        apix_series_dict = {
            "2026-01": 100.0,
            "2026-02": 102.4,
            "2026-03": 105.1,
            "2026-04": 107.8,
            "2026-05": 111.2,
            "2026-06": 114.5,
        }

    res = simulate_cpi_augmentation(
        apix_series=apix_series_dict,
        airfare_weight_in_cpi=req.airfare_weight_in_cpi,
        transport_group_weight=req.transport_group_weight,
        base_period=config.base_period,
    )
    return res.as_dict()
