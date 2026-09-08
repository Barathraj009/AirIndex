"""
AirIndex India — dev_demo reference server
=============================================
IMPORTANT: this is NOT the production backend. The production backend is
backend/app/main.py, built on FastAPI + SQLAlchemy + PostgreSQL as
specified. This Flask server exists only because the current execution
sandbox has no internet access (so `pip install fastapi sqlalchemy
psycopg2 uvicorn` cannot succeed) and no PostgreSQL/Docker available —
see README.md "Environment note" section for details.

Its purpose is narrow but important: prove, by actually running it, that
demo_adapter -> data_processing pipeline -> index_engine -> HTTP JSON API
-> a browser dashboard works end-to-end with zero hand-waving. Every
function this server calls (run_pipeline, compute_index,
compute_index_series, DemoAdapter) is the *exact same code* the real
FastAPI backend imports from backend/app/services/ — nothing here is
reimplemented or faked for the demo.

Run it yourself:
    cd airindex-india
    PYTHONPATH=.:./backend python3 dev_demo/server.py
    # then open http://127.0.0.1:5055/
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from flask import Flask, jsonify, send_from_directory  # noqa: E402

from app.services.data_processing import run_pipeline  # noqa: E402
from app.services.index_engine import IndexConfig, compute_index, compute_index_series  # noqa: E402
from app.services.demo_data_generator import ROUTE_BASKET  # noqa: E402
from ingestion.adapters.demo_adapter import DemoAdapter  # noqa: E402
from ingestion.adapters.base import CollectionRequest  # noqa: E402

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"))

# ---------------------------------------------------------------------
# Build the demo dataset once at startup, exactly the way the real
# ingestion orchestrator would (adapter.run -> data_processing.run_pipeline)
# ---------------------------------------------------------------------
_adapter = DemoAdapter()
_req = CollectionRequest(routes=list(ROUTE_BASKET.keys()), booking_windows=[1, 7, 15, 30, 45],
                          as_of=date(2026, 9, 1))
_raw_df, _adapter_err = _adapter.run(_req)
if _raw_df is None:
    raise RuntimeError(f"Demo adapter unexpectedly unavailable: {_adapter_err}")

CLEAN_DF, QUALITY_REPORT = run_pipeline(_raw_df, source="DEMO_SIMULATED", source_type="DEMO_SIMULATED")

ROUTE_WEIGHTS = {r: w for r, (w, _, _) in ROUTE_BASKET.items()}

# Base/current period must be derived from the data actually generated,
# not hardcoded. Note also that the *edge* months of any collection
# window are naturally thin AND compositionally biased: a travel month
# only gets its T+30/T+45 (cheaper, long-lead) observations once
# collection has been running 30-45+ days against it, so an edge month
# sampled only from its short-lead (expensive) windows will look
# artificially pricier than a fully-sampled month — this is realistic
# behaviour for a live ingestion system (and exactly why a real
# deployment would also exclude/flag under-covered periods), not
# something to hide. For a representative demo snapshot we require a
# period to have observations across ALL configured booking windows
# before treating it as usable for the base/current index calculation.
_valid_df = CLEAN_DF[CLEAN_DF["data_quality_status"] == "VALID"].copy()
_valid_df["_period"] = _valid_df["travel_date"].apply(lambda d: d[:7])
_window_coverage = _valid_df.groupby("_period")["booking_window_days"].nunique()
_ALL_WINDOWS = 5  # T+1, T+7, T+15, T+30, T+45
AVAILABLE_PERIODS = sorted(CLEAN_DF["travel_date"].apply(lambda d: d[:7]).unique())
_fully_covered = sorted([p for p in AVAILABLE_PERIODS if _window_coverage.get(p, 0) >= _ALL_WINDOWS])
BASE_PERIOD = _fully_covered[0] if _fully_covered else AVAILABLE_PERIODS[0]
CURRENT_PERIOD = _fully_covered[-1] if _fully_covered else AVAILABLE_PERIODS[-1]

INDEX_CONFIG = IndexConfig(
    base_period=BASE_PERIOD,
    route_weights=ROUTE_WEIGHTS,
    booking_window_weights={"T+1": 0.30, "T+7": 0.25, "T+15": 0.20, "T+30": 0.15, "T+45": 0.10},
)


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/dashboard/summary")
def dashboard_summary():
    result = compute_index(CLEAN_DF, INDEX_CONFIG, as_of_period=CURRENT_PERIOD)
    return jsonify({
        "index": result.as_dict(),
        "data_quality": QUALITY_REPORT.as_dict(),
        "source_label": "DEMO/SIMULATED",
        "n_routes_tracked": len(ROUTE_WEIGHTS),
        "n_airlines_tracked": CLEAN_DF["airline"].nunique(),
        "current_period": CURRENT_PERIOD,
        "base_period": INDEX_CONFIG.base_period,
    })


@app.get("/api/index/current")
def index_current():
    result = compute_index(CLEAN_DF, INDEX_CONFIG, as_of_period=CURRENT_PERIOD)
    return jsonify(result.as_dict())


@app.get("/api/index/trend")
def index_trend():
    # Only plot periods with full booking-window coverage, for the same
    # reason BASE_PERIOD/CURRENT_PERIOD are chosen that way (see above).
    periods = _fully_covered if _fully_covered else AVAILABLE_PERIODS
    series = compute_index_series(CLEAN_DF, INDEX_CONFIG, periods)
    return jsonify({"series": series, "methodology_version": INDEX_CONFIG.methodology_version,
                     "note": "Only periods with observations across all configured booking windows are shown."})


@app.get("/api/routes")
def routes():
    out = []
    for r, (w, base_fare, tier) in ROUTE_BASKET.items():
        out.append({"route": r, "weight": w, "tier": tier})
    return jsonify({"routes": out, "source_label": "DEMO/SIMULATED"})


@app.get("/api/data-quality/summary")
def data_quality_summary():
    return jsonify({**QUALITY_REPORT.as_dict(), "source_label": "DEMO/SIMULATED"})


@app.get("/api/airlines")
def airlines():
    counts = CLEAN_DF[CLEAN_DF["data_quality_status"] == "VALID"]["airline"].value_counts()
    avg_fare = CLEAN_DF[CLEAN_DF["data_quality_status"] == "VALID"].groupby("airline")["total_fare"].median()
    out = [{"airline": a, "valid_observations": int(counts[a]), "median_fare_inr": round(float(avg_fare[a]), 2)}
           for a in counts.index]
    return jsonify({"airlines": out, "source_label": "DEMO/SIMULATED"})


if __name__ == "__main__":
    print(f"AirIndex India dev_demo server")
    print(f"Loaded {len(CLEAN_DF)} observations, quality: {QUALITY_REPORT.as_dict()}")
    print(f"Current period: {CURRENT_PERIOD}, base period: {INDEX_CONFIG.base_period}")
    app.run(host="127.0.0.1", port=5055, debug=False)
