from contextlib import asynccontextmanager
import logging
import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.rate_limit import RateLimitMiddleware
from app.api.routers import auth, dashboard, index, reference, fares, ingestion, backtesting, admin, exports, analytics, cpi, bulletin, alerts, reports, cpi_airfare, wpi_atf

logger = logging.getLogger(__name__)

settings = get_settings()


def _bootstrap_mospi_refresh() -> None:
    """First-run CPI + WPI bootstrap. Runs on a background thread so a slow
    MoSPI response never blocks app startup or the scheduler thread pool.
    Failures are logged (not fatal) and the daily cron retries."""
    from app.services.scheduler_service import run_cpi_refresh, run_wpi_atf_refresh

    for name, runner in (("CPI", run_cpi_refresh), ("WPI ATF", run_wpi_atf_refresh)):
        try:
            runner()
            logger.info("MoSPI %s bootstrap refresh completed", name)
        except Exception:  # noqa: BLE001 - fixture failure must not crash app
            logger.exception("MoSPI %s bootstrap refresh failed; daily cron will retry", name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 4 scheduled ingestion: background cron that runs all active
    # sources through the same adapter orchestration as manual triggers.
    from app.services.scheduler_service import start_scheduler, shutdown_scheduler

    scheduler_enabled = settings.environment != "test"
    start_scheduler(settings.ingestion_schedule_cron, enabled=scheduler_enabled)

    if scheduler_enabled:
        # First-run MoSPI bootstrap on a background thread so the tables are
        # populated even before the first daily refresh fires.
        threading.Thread(target=_bootstrap_mospi_refresh, name="mospi-bootstrap", daemon=True).start()

    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(
    title="AirIndex India",
    description="Real-time Airfare Price Index for India",
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
app.include_router(cpi.router)
app.include_router(bulletin.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(cpi_airfare.router)
app.include_router(wpi_atf.router)




@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # A last line of defense so an unexpected error (e.g. a bad adapter,
    # per spec section 12) returns a clean 500 rather than leaking a
    # stack trace to the client.
    return JSONResponse(status_code=500, content={"detail": "internal_server_error"})


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "airindex-india-backend"}


@app.get("/")
def root():
    return {"message": "AirIndex India API. See /docs for OpenAPI documentation."}
