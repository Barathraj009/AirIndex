"""
CPI Airfare Index API — serves MoSPI published data directly.

This is the PRIMARY endpoint for the Airfare Price Index.
The MoSPI CPI code 07.3.3.1 IS the official airfare price index.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

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
        raise HTTPException(
            status_code=404,
            detail="No CPI airfare data available. Run ingestion first."
        )

    return {
        "period": latest.period,
        "airfare_index": latest.airfare_index,
        "transport_index": latest.transport_index,
        "general_index": latest.general_index,
        "inflation_yoy": latest.inflation_yoy,
        "base_year": latest.base_year,
        "source": latest.source,
        "source_url": latest.source_url,
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
        raise HTTPException(
            status_code=404,
            detail="No CPI airfare data available."
        )

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

    return {"periods": [p[0] for p in periods]}


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
        raise HTTPException(status_code=404, detail="No CPI data available.")

    comparison = []
    for rec in reversed(records):
        comparison.append({
            "period": rec.period,
            "airfare": rec.airfare_index,
            "transport": rec.transport_index,
            "general": rec.general_index,
        })

    return {
        "series": comparison,
        "base_year": "2024=100",
        "note": "All indices use base year 2024=100",
    }
