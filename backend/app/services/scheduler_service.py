"""APScheduler wiring: periodic ingestion for AirIndex India's two live product
data sources.

  * ``GOOGLE_FLIGHTS_API`` — live Google Flights fare observations collected by
    the GDS adapter orchestration (same idempotent path as the manual
    /api/ingestion/trigger endpoint).
  * ``MOSPI_CPI``         — official MoSPI CPI airfare index (07.3.3.1,
    base 2024=100), refreshed daily so the official history is always current.

Both jobs reuse the manual ingestion orchestration (idempotent upserts) so a
missed or duplicate cron fire is always safe."""

import logging
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# Last refresh outcome per source key ("google_flights", "cpi"). Populated by
# the refresh runners so the API can surface *_last_refresh_error without a
# live per-source DB poll.
REFRESH_OUTCOMES: dict[str, dict] = {}


def _record_refresh_outcome(source_key: str, error: Exception | None, n_records: int | None = None) -> None:
    REFRESH_OUTCOMES[source_key] = (
        {"ok": True, "ts": time.time(), "records": n_records}
        if error is None
        else {"ok": False, "ts": time.time(), "error": f"{type(error).__name__}: {error}"}
    )


def run_scheduled_google_ingestion() -> None:
    """Collect live Google Flights fare observations for the route basket. Runs
    through the same adapter orchestration as the manual trigger so scheduled
    and manual runs behave identically. Failures are surfaced via
    REFRESH_OUTCOMES (never crash the scheduler)."""
    db = SessionLocal()
    try:
        from app.services.ingestion_runner import collect_from_sources

        n = collect_from_sources(db, triggered_by="scheduler", run_action="SCHEDULED_INGESTION")
        _record_refresh_outcome("google_flights", None, n_records=n)
        logger.info("Scheduled Google Flights ingestion complete: %d observations", n)
    except Exception:  # noqa: BLE001 - a job failure must not kill the scheduler
        db.rollback()
        raise
    finally:
        db.close()


def run_cpi_refresh() -> None:
    """Fetch the official MoSPI CPI airfare index (07.3.3.1, base 2024=100) and
    upsert into the cpi_airfare_index table. Uses the same upsert path as the
    manual refresh; a CPI refresh failure is surfaced via REFRESH_OUTCOMES
    rather than crashing the scheduler."""
    db = SessionLocal()
    try:
        from ingestion.adapters.mospi_cpi import fetch_mospi_cpi_airfare
        from app.models.cpi import CpiAirfareIndex
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        records = fetch_mospi_cpi_airfare()
        inserted = 0
        for rec in records:
            result = db.execute(
                pg_insert(CpiAirfareIndex)
                .values(**rec)
                .on_conflict_do_nothing(index_elements=[CpiAirfareIndex.period])
            )
            inserted += result.rowcount
        db.commit()
        _record_refresh_outcome("cpi", None, n_records=len(records))
        logger.info("MoSPI CPI airfare refresh complete: %d records", len(records))
    except Exception as exc:  # noqa: BLE001 - CPI refresh failure must not crash scheduler
        db.rollback()
        _record_refresh_outcome("cpi", exc)
        raise
    finally:
        db.close()


scheduler = BackgroundScheduler(timezone="UTC")


def start_scheduler(cron_expr: str, enabled: bool = True) -> bool:
    """Configure and start the background scheduler. Returns False (and leaves
    the scheduler stopped) when disabled for tests/dev."""
    if not enabled or scheduler.running:
        return False
    scheduler.add_job(
        run_scheduled_google_ingestion,
        CronTrigger.from_crontab(cron_expr),
        id="google_flights_ingestion",
        name="Collect Google Flights fare observations",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    # Refresh the official MoSPI CPI airfare index daily at 06:00 UTC so the
    # graph always serves the latest official published figures.
    scheduler.add_job(
        run_cpi_refresh,
        CronTrigger(hour=6, minute=0),
        id="cpi_refresh",
        name="Refresh MoSPI CPI airfare index",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    return True


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
