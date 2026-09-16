"""Real-data source status derivation (the 2-source product monitor).

The AirIndex service now serves exactly two real data sources:

* ``GOOGLE_FLIGHTS_API`` — licensed Google Flights fares via RapidAPI
  (gds_adapter). Drives APIx (the live component of the combined airfare
  index). Reported ``LIVE`` while a successful collection is within the
  live window; otherwise ``UNAVAILABLE`` with the last failure reason.
* ``MOSPI_CPI`` — the official MoSPI CPI airfare index (07.3.3.1,
  base 2024=100), refreshed by the scheduler and used to anchor official
  history. Reported ``LIVE`` whenever at least one row exists.

Status is derived entirely from the database — the router never makes
network calls, so this endpoint is safe to poll and never blocks on a slow
upstream."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.cpi import CpiAirfareIndex
from app.models.ingestion import IngestionRun
from app.models.reference import DataSource

logger = logging.getLogger(__name__)

LIVE_SOURCE = "GOOGLE_FLIGHTS_API"
MOSPI_SOURCE = "MOSPI_CPI"
_LIVE_WINDOW = timedelta(days=15)

_SOURCE_LABELS = {
    "GOOGLE_FLIGHTS_API": {
        "label": "Google Flights",
        "category": "API",
        "detail": "Licensed Google Flights fare feed via RapidAPI (gds_adapter).",
    },
    "MOSPI_CPI": {
        "label": "MoSPI CPI (Airfare)",
        "category": "PUBLIC_DATASET",
        "detail": "Official airfare CPI, code 07.3.3.1, base 2024=100, source esankhyiki.mospi.gov.in.",
    },
}


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _last_run(db: Session, source_id: int | None) -> dict:
    if source_id is None:
        return {}
    run = (
        db.query(IngestionRun)
        .filter(IngestionRun.data_source_id == source_id)
        .order_by(IngestionRun.started_at.desc())
        .first()
    )
    if run is None:
        return {}
    return {
        "last_run_status": run.status,
        "last_run_at": _iso(run.started_at),
    }


def build_sources_status(db: Session) -> dict:
    """Return ``{sources: [...], summary: {...}, as_of}`` describing the
    live status of the two product data sources."""
    now = datetime.now(timezone.utc)

    rows = db.query(IngestionRun).all() if False else (
        db.query(IngestionRun).order_by(IngestionRun.started_at.desc()).all()
    )
    latest_run_by_source: dict[int, IngestionRun] = {}
    for r in rows:
        latest_run_by_source.setdefault(r.data_source_id, r)

    ds_by_name: dict[str, DataSource] = {
        d.name: d for d in db.query(DataSource).all()
    }

    sources = []
    for name in (LIVE_SOURCE, MOSPI_SOURCE):
        ds = ds_by_name.get(name)
        label = _SOURCE_LABELS[name]
        if name == "GOOGLE_FLIGHTS_API":
            # Live as long as the most recent successful Google collection is
            # within the live window.
            recent_ok = [
                r for r in latest_run_by_source.values()
                if r.data_source_id == (ds.id if ds else -1)
                and r.status in ("SUCCESS", "SERVICE_UNAVAILABLE")
            ]
            ok = next((r for r in recent_ok if r.status == "SUCCESS"), None)
            if ok is not None and ok.completed_at and (now - ok.completed_at) <= _LIVE_WINDOW:
                status = "LIVE"
            elif ok is not None:
                status = "STALE"
            else:
                status = "UNAVAILABLE"
            fail = next(
                (r for r in latest_run_by_source.values()
                 if r.data_source_id == (ds.id if ds else -1) and r.status == "FAILED"),
                None,
            )
            last_failure_reason = fail.error_message if fail else None
            last_success_at = ok.completed_at if ok and ok.status == "SUCCESS" else None
            detail = label["detail"]
            if status == "LIVE":
                detail += " Live fare feed — used for APIx."
        else:
            # MOSPI_CPI: LIVE whenever any row has been ingested (official
            # history anchor). No per-second freshness window — the schedule
            # refreshes it monthly-ish.
            latest_cpi = (
                db.query(CpiAirfareIndex)
                .order_by(CpiAirfareIndex.period.desc())
                .first()
            )
            if latest_cpi is not None:
                status = "LIVE"
                last_success_at = latest_cpi.fetched_at
                last_failure_reason = None
                detail = (
                    label["detail"]
                    + f" Latest published period {latest_cpi.period} "
                      f"(index {latest_cpi.airfare_index:,.2f})."
                )
            else:
                status = "UNAVAILABLE"
                last_success_at = None
                last_failure_reason = "No CPI rows yet — scheduled MoSPI refresh has not run."
                detail = label["detail"]

        run = latest_run_by_source.get(ds.id) if ds else None
        sources.append(
            {
                "source_name": name,
                "label": label["label"],
                "category": label["category"],
                "status": status,
                "last_success_at": _iso(last_success_at),
                "last_failure_reason": last_failure_reason,
                "last_run_at": _iso(run.started_at) if run else None,
                "last_run_status": run.status if run else None,
                "detail": detail,
            }
        )

    by_status: dict[str, int] = {}
    for s in sources:
        by_status[s["status"]] = by_status.get(s["status"], 0) + 1

    return {
        "sources": sources,
        "summary": {
            "total": len(sources),
            "by_status": by_status,
        },
        "as_of": _iso(now),
    }