"""Combined airfare price-index series (the single curve the product shows).

The graph across Dashboard / Data / Analysis is built from exactly TWO real
data sources:

* Official MoSPI CPI airfare index — code 07.3.3.1, base 2024=100, stored in
  ``cpi_airfare_index`` (published history, refreshed by the scheduler).
* APIx computed by ``index_engine`` from live Google Flights observations
  (``GOOGLE_FLIGHTS_API``, collected by the gds_adapter) from the first month
  that has live data.

Chaining: the official history is rescaled by a constant so its last published
value equals APIx at the first live month. Constant rescaling preserves every
official month-on-month and year-on-year change; it only re-bases the series to
a common scale. Every point is labelled with its ``source`` so official values
can never be confused with real-time measurements.
"""

from datetime import datetime, timezone

from app.api.query_helpers import active_route_weights, load_observations_df
from app.models.cpi import CpiAirfareIndex
from app.services.index_engine import IndexConfig, compute_index_series

MOSPI_SOURCE = "MOSPI_CPI"
LIVE_SOURCE = "GOOGLE_FLIGHTS_API"

_BASE_YEAR = "2024=100"


def resolve_base_period(configured: str | None, periods: list[str]) -> str | None:
    """Return the effective index base: the configured base when it has data,
    otherwise the earliest available period (real-data bootstrap)."""
    if not periods:
        return None
    if configured and configured in periods:
        return configured
    return periods[0]


def _live_apix_series(db) -> tuple[dict, str | None]:
    """Compute APIx per month strictly from GOOGLE_FLIGHTS_API observations."""
    df = load_observations_df(db)
    if df.empty:
        return {}, None
    df = df[df["source"] == LIVE_SOURCE]
    periods = sorted(df["travel_date"].str[:7].unique().tolist())
    if not periods:
        return {}, None
    weights = active_route_weights(db)
    config = IndexConfig(base_period=periods[0], route_weights=weights)
    computed = compute_index_series(df, config, periods)
    points = {}
    for pt in computed:
        if pt.get("index_value") is not None and pt.get("period"):
            points[pt["period"]] = pt["index_value"]
    return points, periods[0]


def _official_series(db) -> dict:
    records = (
        db.query(CpiAirfareIndex)
        .order_by(CpiAirfareIndex.period.asc())
        .all()
    )
    return {
        rec.period: {
            "airfare_index": rec.airfare_index,
            "inflation_yoy": rec.inflation_yoy,
        }
        for rec in records
    }


def _yoy(ordered_points: list[dict]) -> None:
    by_period = {p["period"]: p["airfare_index"] for p in ordered_points if p.get("airfare_index") is not None}
    for p in ordered_points:
        year, month_str = p["period"].split("-", 1)
        prev_period = f"{int(year) - 1}-{month_str}"
        if prev_period in by_period and by_period[prev_period]:
            p["inflation_yoy"] = (p["airfare_index"] / by_period[prev_period] - 1) * 100


def build_combined_series(db, months: int | None = None) -> dict:
    """Build the combined airfare series: rebased MoSPI history + APIx live.

    Returns:
    {
      "available": bool,
      "series": [{period, airfare_index, inflation_yoy, source}, ...],
      "transition_period": str | None,
      "base_year": "2024=100",
      "source": "MOSPI_CPI + GOOGLE_FLIGHTS_API",
      "note": str,
    }
    """
    official = _official_series(db)
    live_pts, transition = _live_apix_series(db)

    if not official and not live_pts:
        return {
            "available": False,
            "series": [],
            "transition_period": None,
            "base_year": _BASE_YEAR,
            "source": f"{MOSPI_SOURCE} + {LIVE_SOURCE}",
            "note": "No airfare index data available yet.",
        }

    scale = None
    official_periods = sorted(official)
    if live_pts and official_periods:
        # Chain link: rebase official history so its last published value
        # sits at the same level as APIx on the first live month.
        last_official_val = official[official_periods[-1]]["airfare_index"]
        if last_official_val:
            scale = live_pts[transition] / last_official_val

    points: list[dict] = []
    for period in official_periods:
        rec = official[period]
        value = rec["airfare_index"] * scale if scale else rec["airfare_index"]
        points.append({
            "period": period,
            "airfare_index": value,
            "inflation_yoy": rec["inflation_yoy"],
            "source": MOSPI_SOURCE,
        })
    for period in sorted(live_pts):
        points.append({
            "period": period,
            "airfare_index": live_pts[period],
            "inflation_yoy": None,
            "source": LIVE_SOURCE,
        })

    points.sort(key=lambda p: p["period"])

    # Fill YoY for the live segment (and any gaps) so inflation is continuous.
    _yoy(points)

    if months:
        if months <= 0:
            points = []
        else:
            points = points[-months:]

    note_suffix = ""
    if scale and transition:
        note_suffix = (
            f" Official MoSPI history (through {official_periods[-1]}) is rebased to a common "
            f"base with the live APIx series ({transition} = 100); rebasing preserves all "
            "official month-on-month and year-on-year changes."
        )

    return {
        "available": True,
        "series": points,
        "transition_period": transition,
        "base_year": _BASE_YEAR,
        "source": f"{MOSPI_SOURCE} + {LIVE_SOURCE}",
        "note": "Airfare index curve = official MoSPI CPI (07.3.3.1, base 2024=100) chained "
                f"to the APIx live index (Google Flights fares).{note_suffix}",
    }


def current_airfare(db) -> dict:
    """Latest combined airfare point + series metadata for the hero cards."""
    combined = build_combined_series(db)
    if not combined["available"] or not combined["series"]:
        return {
            "available": False,
            "period": None,
            "airfare_index": None,
            "inflation_yoy": None,
            "source": combined["source"],
            "base_year": _BASE_YEAR,
            "source_url": "https://esankhyiki.mospi.gov.in",
            "cpi_code": "07.3.3.1",
            "transition_period": None,
            "fetched_at": None,
            "note": combined["note"],
        }
    latest = combined["series"][-1]
    fetched = db.query(CpiAirfareIndex).order_by(CpiAirfareIndex.fetched_at.desc()).first()
    return {
        "available": True,
        "period": latest["period"],
        "airfare_index": latest["airfare_index"],
        "inflation_yoy": latest["inflation_yoy"],
        "source": latest["source"],
        "base_year": _BASE_YEAR,
        "source_url": "https://esankhyiki.mospi.gov.in",
        "cpi_code": "07.3.3.1",
        "transition_period": combined["transition_period"],
        "fetched_at": fetched.fetched_at.isoformat() if fetched and fetched.fetched_at else datetime.now(timezone.utc).isoformat(),
        "note": combined["note"],
    }


def available_periods(db) -> list[str]:
    combined = build_combined_series(db)
    return [p["period"] for p in combined["series"]]