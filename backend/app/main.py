"""AirIndex India API entrypoint — the live-data product graph.

Route/basket and replay fixtures moved to `app/data/`; the demo/scraper/WPI-ATF/
DGCA "evaluation" scaffolding was removed in the real-data re-scope (R2). The public
API now serves exactly two real sources and nothing else:

  * GOOGLE_FLIGHTS_API — live Google Flights fare observations collected by the
    gds_adapter orchestration in `app/services/ingestion_runner.py`.
  * MOSPI_CPI         — official MoSPI CPI airfare index (07.3.3.1, base 2024=100)
    refreshed through the same MoSPI MoSPI upsert path as /api/ingestion.

Both are refreshed by the same adapter orchestration as the manual trigger, on a
UTC cron. The graph the frontend draws is the combined series (official index +
APIx live fares) built by `app/services/combined_series.py`.
"""

from contextlib import asynccontextmanager
import logging
import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.rate_limit import RateLimitMiddleware
from app.api.routers import (
    auth, dashboard, index, reference, fares, ingestion, backtesting, admin,
    exports, analytics, cpi_airfare, bulletin, alerts, reports, sources,
)

logger = logging.getLogger(__name__)

settings = get_settings()


def _bootstrap_external_refresh() -> None:
    """First-run bootstrap of the one product data source that needs a live
    refresh before the graph can be drawn: the official MoSPI CPI airfare
    index (07.3.3.1, base 2024=100). Runs on a background thread so a slow
    MoSPI response never blocks app startup or the scheduler thread pool.
    Failures are logged (not fatal) and the scheduled job retries.

    The live Google Flights component is collected by the gds_adapter through
    the scheduled ingestion; it does not run here."""
    from app.services.scheduler_service import run_cpi_refresh

    try:
        run_cpi_refresh()
        logger.info("MoSPI CPI airfare bootstrap refresh completed")
    except Exception:  # noqa: BLE001 - bootstrap failure must not crash app
        logger.exception("MoSPI CPI bootstrap refresh failed; scheduled job will retry")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Scheduled ingestion: runs the two real sources (GOOGLE_FLIGHTS_API via the
    # gds_adapter and the official MoSPI CPI airfare index) through the same
    # adapter orchestration as the manual /api/ingestion/trigger.
    from app.services.scheduler_service import start_scheduler, shutdown_scheduler

    scheduler_enabled = settings.environment != "test"
    start_scheduler(settings.ingestion_schedule_cron, enabled=scheduler_enabled)

    if scheduler_enabled:
        threading.Thread(target=_bootstrap_external_refresh, name="cpi-bootstrap", daemon=True).start()

    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(
    title="AirIndex India",
    description="Real-time Airfare Price Index for India (APIx + official MoSPI CPI airfare)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.api_rate_limit_per_minute)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(index.router)
app.include_router(reference.router)
app.include_router(fares.router)
app.include_router(ingestion.router)
app.include_router(backtesting.router)
app.include_router(admin.router)
app.include_router(exports.router)
app.include_router(analytics.router)
app.include_router(cpi_airfare.router)
app.include_router(bulletin.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(sources.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # A last line of defense so an unexpected error (e.g. a bad adapter,
    # per spec section 12) returns a clean 500 rather than leaking a stack
    # trace to the client.
    return JSONResponse(status_code=500, content={"detail": "internal_server_error"})


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "airindex-india-backend"}


@app.get("/")
def root():
    return {"message": "AirIndex India API. See /docs for OpenAPI documentation."}
