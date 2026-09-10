"""APScheduler wiring (Phase 4): periodic ingestion runs using the same
adapter orchestration as the manual /api/scraping/trigger endpoint. The
schedule is configured via `ingestion_schedule_cron` (default every 6h).

Also periodically refreshes the MoSPI CPI airfare index table so the
frontend always serves fresh official government data.

The scheduled job reuses collect_from_sources, which is idempotent
(ON CONFLICT observation_id DO NOTHING), so missed/duplicate cron fires
are safe.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.database import SessionLocal
from app.services.ingestion_runner import collect_from_sources


def run_scheduled_ingestion() -> None:
    """Entry point the scheduler fires on cron. Runs in APScheduler's own
    threadpool; swallows/exposes outcomes via ingestion_runs rows (never
    crashes the scheduler)."""
    db = SessionLocal()
    try:
        collect_from_sources(db, triggered_by="scheduler", run_action="SCHEDULED_INGESTION")
    except Exception:  # noqa: BLE001 - a job failure must not kill the scheduler
        db.rollback()
        raise
    finally:
        db.close()


def run_cpi_refresh() -> None:
    """Fetch MoSPI CPI data and upsert into cpi_airfare_index table."""
    db = SessionLocal()
    try:
        from ingestion.adapters.mospi_cpi import fetch_mospi_airfare_index
        from app.models.cpi import CpiAirfareIndex
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        records = fetch_mospi_airfare_index()
        inserted = 0
        for rec in records:
            result = db.execute(
                pg_insert(CpiAirfareIndex)
                .values(**rec)
                .on_conflict_do_nothing(index_elements=[CpiAirfareIndex.period])
            )
            inserted += result.rowcount
        db.commit()
    except Exception:  # noqa: BLE001 - CPI refresh failure must not kill scheduler
        db.rollback()
        raise
    finally:
        db.close()


scheduler = BackgroundScheduler(timezone="UTC")


def start_scheduler(cron_expr: str, enabled: bool = True) -> bool:
    """Configure and start the background scheduler. Returns False (and
    leaves the scheduler stopped) when disabled for tests/dev."""
    if not enabled or scheduler.running:
        return False
    scheduler.add_job(
        run_scheduled_ingestion,
        CronTrigger.from_crontab(cron_expr),
        id="scheduled_ingestion",
        name="Run all active ingestion sources",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    # Refresh MoSPI CPI daily at 06:00 UTC
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