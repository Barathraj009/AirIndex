from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.rate_limit import RateLimitMiddleware
from app.api.routers import auth, dashboard, index, reference, fares, ingestion, backtesting, admin, exports, analytics, cpi, bulletin, alerts, reports

settings = get_settings()




@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 4 scheduled ingestion: background cron that runs all active
    # sources through the same adapter orchestration as manual triggers.
    from app.services.scheduler_service import start_scheduler, shutdown_scheduler

    scheduler_enabled = settings.environment != "test"
    start_scheduler(settings.ingestion_schedule_cron, enabled=scheduler_enabled)
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
