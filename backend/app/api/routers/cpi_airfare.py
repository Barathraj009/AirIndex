"""
CPI Airfare Index API — serves MoSPI published data directly.

This is the PRIMARY endpoint for the Airfare Price Index.
The MoSPI CPI code 07.3.3.1 IS the official airfare price index.

All endpoints return 200 even when the table is empty (with
`available: false`) so the UI can show a clean "awaiting data" state
instead of an error banner during first-run bootstrap.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.models.cpi import CpiAirfareIndex

router = APIRouter(prefix="/api/cpi-airfare", tags=["cpi-airfare"])


@router.get("/current")
def get_current_airfare_index(
    db: Session = Depends(get_db),
    _=Depends(require_permission("view_dashboard"))
):
    """Get the latest MoSPI CPI airfare index value."""
    latest = (
        db.query(CpiAirfareIndex)
        .order_by(CpiAirfareIndex.period.desc())
        .first()
    )

    if not latest:
        return {
            "available": False,
            "period": None,
            "airfare_index": None,
            "transport_index": None,
            "general_index": None,
            "inflation_yoy": None,
            "base_year": "2024=100",
            "source": "MOSPI_CPI",
            "source_url": "https://esankhyiki.mospi.gov.in",
            "cpi_code": "07.3.3.1",
            "fetched_at": None,
        }

    return {
        "available": True,
        "period": latest.period,
        "airfare_index": latest.airfare_index,
        "transport_index": latest.transport_index,
        "general_index": latest.general_index,
        "inflation_yoy": latest.inflation_yoy,
        "base_year": latest.base_year,
        "source": latest.source,
        "source_url": latest.source_url,
        "cpi_code": latest.cpi_code,
        "fetched_at": latest.fetched_at.isoformat() if latest.fetched_at else None,
    }


@router.get("/trend")
def get_airfare_trend(
    months: int = 12,
    db: Session = Depends(get_db),
    _=Depends(require_permission("view_dashboard"))
):
    """Get CPI airfare index trend for the last N months."""
    records = (
        db.query(CpiAirfareIndex)
        .order_by(CpiAirfareIndex.period.desc())
        .limit(months)
        .all()
    )

    if not records:
        return {
            "available": False,
            "series": [],
            "base_year": "2024=100",
            "source": "MOSPI_CPI",
            "cpi_code": "07.3.3.1",
        }

    trend = []
    for rec in reversed(records):  # Chronological order
        trend.append({
            "period": rec.period,
            "airfare_index": rec.airfare_index,
            "transport_index": rec.transport_index,
            "general_index": rec.general_index,
            "inflation_yoy": rec.inflation_yoy,
        })

    return {
        "available": True,
        "series": trend,
        "base_year": "2024=100",
        "source": "MOSPI_CPI",
        "cpi_code": "07.3.3.1",
    }


@router.get("/available-periods")
def get_available_periods(
    db: Session = Depends(get_db),
    _=Depends(require_permission("view_dashboard"))
):
    """Get list of available periods in the database."""
    periods = (
        db.query(CpiAirfareIndex.period)
        .order_by(CpiAirfareIndex.period.desc())
        .all()
    )

    return {
        "available": len(periods) > 0,
        "periods": [p[0] for p in periods],
    }


@router.get("/comparison")
def get_cpi_comparison(
    db: Session = Depends(get_db),
    _=Depends(require_permission("view_dashboard"))
):
    """Compare airfare CPI with transport and general CPI."""
    records = (
        db.query(CpiAirfareIndex)
        .order_by(CpiAirfareIndex.period.desc())
        .limit(12)
        .all()
    )

    if not records:
        return {
            "available": False,
            "series": [],
            "base_year": "2024=100",
            "note": "All indices use base year 2024=100",
        }

    comparison = []
    for rec in reversed(records):
        comparison.append({
            "period": rec.period,
            "airfare": rec.airfare_index,
            "transport": rec.transport_index,
            "general": rec.general_index,
        })

    return {
        "available": True,
        "series": comparison,
        "base_year": "2024=100",
        "note": "All indices use base year 2024=100",
    }