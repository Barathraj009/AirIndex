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

import logging
import time

from app.core.database import SessionLocal
from app.services.ingestion_runner import collect_from_sources

logger = logging.getLogger(__name__)

# Last MoSPI refresh outcome per source key (e.g. "wpi_atf", "cpi").
# Populated by refresh runners so the API can surface *_last_refresh_error.
LAST_MOSPI_REFRESH: dict[str, dict] = {}


def _record_mospi_outcome(source: str, error: Exception | None, n_records: int | None = None) -> None:
    LAST_MOSPI_REFRESH[source] = (
        {"ok": True, "ts": time.time(), "records": n_records}
        if error is None
        else {"ok": False, "ts": time.time(), "error": f"{type(error).__name__}: {error}"}
    )


def _fetch_with_retry(fetcher, source: str, retries: int = 3) -> list:
    """Call a MoSPI fetch with retry + backoff. MoSPI occasionally hiccups
    (throttle/reset) and a retry usually succeeds."""
    delays = (1, 3, 9)
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            result = fetcher()
            _record_mospi_outcome(source, None, n_records=len(result))
            return result
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last_exc = exc
            if attempt < retries - 1:
                logger.warning("MoSPI %s fetch attempt %d/%d failed: %s; retrying", source, attempt + 1, retries, exc)
                time.sleep(delays[min(attempt, len(delays) - 1)])
    logger.error("MoSPI %s fetch failed after %d attempts: %s", source, retries, last_exc)
    _record_mospi_outcome(source, last_exc)
    raise last_exc  # type: ignore[misc]


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

        records = _fetch_with_retry(fetch_mospi_airfare_index, source="cpi")
        inserted = 0
        for rec in records:
            result = db.execute(
                pg_insert(CpiAirfareIndex)
                .values(**rec)
                .on_conflict_do_nothing(index_elements=[CpiAirfareIndex.period])
            )
            inserted += result.rowcount
        db.commit()
        _record_mospi_outcome("cpi", None)
    except Exception as exc:  # noqa: BLE001 - CPI refresh failure must not kill scheduler
        db.rollback()
        _record_mospi_outcome("cpi", exc)
        raise
    finally:
        db.close()


def run_wpi_atf_refresh() -> None:
    """Fetch MoSPI WPI ATF data and upsert into wpi_atf_index table."""
    db = SessionLocal()
    try:
        from ingestion.adapters.mospi_wpi import fetch_mospi_wpi_atf
        from app.models.wpi_atf import WpiAtfIndex
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        records = _fetch_with_retry(fetch_mospi_wpi_atf, source="wpi_atf")
        inserted = 0
        for rec in records:
            result = db.execute(
                pg_insert(WpiAtfIndex)
                .values(**rec)
                .on_conflict_do_nothing(index_elements=[WpiAtfIndex.period])
            )
            inserted += result.rowcount
        db.commit()
        _record_mospi_outcome("wpi_atf", None)
    except Exception as exc:  # noqa: BLE001 - WPI refresh failure must not kill scheduler
        db.rollback()
        _record_mospi_outcome("wpi_atf", exc)
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
    # Refresh MoSPI WPI ATF daily at 06:10 UTC (after CPI)
    scheduler.add_job(
        run_wpi_atf_refresh,
        CronTrigger(hour=6, minute=10),
        id="wpi_atf_refresh",
        name="Refresh MoSPI WPI ATF fuel-cost index",
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