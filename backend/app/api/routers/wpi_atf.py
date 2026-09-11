"""
WPI ATF (Aviation Turbine Fuel) API — serves MoSPI wholesale price data.

The WPI ATF index (base 2022-23=100) is the official fuel-cost input used
in the "Fuel-cost vs Airfare" comparison. All endpoints return 200 even
when the table is empty (with ``available: false``) so the UI can show a
clean waiting state instead of an error banner.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.models.wpi_atf import WpiAtfIndex
from app.models.cpi import CpiAirfareIndex

router = APIRouter(prefix="/api/wpi-atf", tags=["wpi-atf"])

BASE_META = {
    "base_year": "2022-23=100",
    "source": "MOSPI_WPI",
    "source_url": "https://esankhyiki.mospi.gov.in",
    "wpi_code": "1202010004",
}


@router.get("/series")
def get_wpi_atf_series(
    months: int = 12,
    db: Session = Depends(get_db),
    _=Depends(require_permission("view_dashboard")),
):
    """Get WPI ATF index trend for the last N months."""
    records = (
        db.query(WpiAtfIndex)
        .order_by(WpiAtfIndex.period.desc())
        .limit(months)
        .all()
    )

    if not records:
        return {
            "available": False,
            "series": [],
            **BASE_META,
        }

    series = []
    for rec in reversed(records):  # Chronological order
        series.append({
            "period": rec.period,
            "atf_index": rec.atf_index,
            "inflation_mom": rec.inflation_mom,
            "inflation_yoy": rec.inflation_yoy,
        })

    return {
        "available": True,
        "series": series,
        **BASE_META,
    }


@router.get("/fuel-vs-airfare")
def get_fuel_vs_airfare(
    months: int = 24,
    db: Session = Depends(get_db),
    _=Depends(require_permission("view_dashboard")),
):
    """Compare WPI ATF fuel cost with the CPI airfare series.

    The two official series use different bases (WPI 2022-23=100,
    CPI 2024=100), so both are rebased to 100 at the first common month
    so the comparison shows *relative movement* only. Raw values are
    included alongside the rebased series.
    """
    cpi_records = (
        db.query(CpiAirfareIndex)
        .order_by(CpiAirfareIndex.period.desc())
        .limit(months)
        .all()
    )
    atf_records = (
        db.query(WpiAtfIndex)
        .order_by(WpiAtfIndex.period.desc())
        .limit(months)
        .all()
    )

    if not atf_records:
        return {
            "available": False,
            "rebase_period": None,
            "series": [],
            "note": "WPI ATF data is not available yet.",
            "atf_base_year": BASE_META["base_year"],
            "airfare_base_year": "2024=100",
        }

    cpi_map = {r.period: r.airfare_index for r in cpi_records}
    atf_map = {r.period: r.atf_index for r in atf_records}

    # Only periods where both series exist.
    common = sorted(set(cpi_map) & set(atf_map))
    if not common:
        return {
            "available": False,
            "rebase_period": None,
            "series": [],
            "note": "No overlapping periods yet between WPI ATF and CPI airfare.",
            "atf_base_year": BASE_META["base_year"],
            "airfare_base_year": "2024=100",
        }

    rebase_period = common[0]
    cpi_base = cpi_map[rebase_period] or 100.0
    atf_base = atf_map[rebase_period] or 100.0

    series = []
    for p in common:
        cpi, atf = cpi_map[p], atf_map[p]
        series.append({
            "period": p,
            "airfare_index": cpi,
            "atf_index": atf,
            "airfare_rebased": round((cpi / cpi_base) * 100, 2) if cpi_base else None,
            "atf_rebased": round((atf / atf_base) * 100, 2) if atf_base else None,
        })

    return {
        "available": True,
        "rebase_period": rebase_period,
        "series": series,
        "note": f"Both series rebased to 100 at {rebase_period} for comparability.",
        "atf_base_year": BASE_META["base_year"],
        "airfare_base_year": "2024=100",
    }


@router.get("/current")
def get_current_wpi_atf(
    db: Session = Depends(get_db),
    _=Depends(require_permission("view_dashboard")),
):
    """Get the latest MoSPI WPI ATF index value."""
    latest = (
        db.query(WpiAtfIndex)
        .order_by(WpiAtfIndex.period.desc())
        .first()
    )

    if not latest:
        return {
            "available": False,
            "period": None,
            "atf_index": None,
            "inflation_mom": None,
            "inflation_yoy": None,
            "fetched_at": None,
            **BASE_META,
        }

    return {
        "available": True,
        "period": latest.period,
        "atf_index": latest.atf_index,
        "inflation_mom": latest.inflation_mom,
        "inflation_yoy": latest.inflation_yoy,
        "fetched_at": latest.fetched_at.isoformat() if latest.fetched_at else None,
        **BASE_META,
    }