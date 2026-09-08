from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.api.query_helpers import load_observations_df

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/lead-time")
def lead_time_analysis(origin: str, destination: str, db: Session = Depends(get_db),
                        _=Depends(require_permission("view_dashboard"))):
    """For a given route: median fare by booking window (T+1..T+45), so
    the frontend can show how fare rises as departure approaches (spec
    section 7)."""
    df = load_observations_df(db, origin=origin, destination=destination)
    df = df[df["data_quality_status"] == "VALID"]
    if df.empty:
        raise HTTPException(status_code=404, detail="no_valid_data_for_route")

    grouped = df.groupby("booking_window_days")["total_fare"].median().sort_index()
    points = [{"booking_window_days": int(w), "median_fare": round(float(v), 2)} for w, v in grouped.items()]

    if len(points) >= 2:
        cheapest = min(points, key=lambda p: p["median_fare"])
        most_expensive = max(points, key=lambda p: p["median_fare"])
        pct_increase = round((most_expensive["median_fare"] / cheapest["median_fare"] - 1) * 100, 2)
    else:
        pct_increase = None

    return {"origin": origin, "destination": destination, "points": points,
            "pct_increase_last_minute_vs_cheapest": pct_increase}


@router.get("/lead-time/all-routes-summary")
def lead_time_all_routes(db: Session = Depends(get_db), _=Depends(require_permission("view_dashboard"))):
    """Ranks routes by how sharply fares increase as travel approaches
    (T+1 vs T+45), for the "identify routes where prices increase
    sharply" requirement in spec section 7."""
    df = load_observations_df(db)
    df = df[df["data_quality_status"] == "VALID"]
    if df.empty:
        return {"routes": []}

    out = []
    for (origin, dest), sub in df.groupby(["origin", "destination"]):
        grouped = sub.groupby("booking_window_days")["total_fare"].median()
        if 1 in grouped.index and 45 in grouped.index:
            pct = round((grouped[1] / grouped[45] - 1) * 100, 2)
            out.append({"route": f"{origin}-{dest}", "t1_vs_t45_pct_increase": pct})

    out.sort(key=lambda r: r["t1_vs_t45_pct_increase"], reverse=True)
    return {"routes": out}


@router.get("/airlines")
def airline_analysis(db: Session = Depends(get_db), _=Depends(require_permission("view_dashboard"))):
    df = load_observations_df(db)
    df = df[df["data_quality_status"] == "VALID"]
    if df.empty:
        return {"airlines": []}

    grouped = df.groupby("airline").agg(
        valid_observations=("total_fare", "count"),
        median_fare=("total_fare", "median"),
    ).reset_index()
    total = grouped["valid_observations"].sum()
    grouped["observation_share_pct"] = (grouped["valid_observations"] / total * 100).round(2)
    grouped = grouped.sort_values("valid_observations", ascending=False)

    return {"airlines": grouped.round(2).to_dict("records")}
