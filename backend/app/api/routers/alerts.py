from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission, get_current_user
from app.services.alerts import check_alert, check_and_notify
from app.models.auth import User

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/check")
def alert_check(current_user: User = Depends(require_permission("view_alerts"))):
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        result = check_alert()
        return result
    finally:
        db.close()


@router.post("/check-and-notify")
def alert_check_and_notify(current_user: User = Depends(require_permission("manage_alerts"))):
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        result = check_and_notify()
        return result
    finally:
        db.close()


@router.get("/status")
def alert_status(current_user: User = Depends(require_permission("view_alerts"))):
    import os
    return {
        "enabled": os.getenv("ALERT_ENABLED", "True").lower() in ("1", "true", "yes"),
        "threshold_pct": float(os.getenv("ALERT_THRESHOLD_PCT", "10.0")),
        "cooldown_hours": int(os.getenv("ALERT_COOLDOWN_HOURS", "24")),
        "smtp_configured": bool(os.getenv("ALERT_SMTP_HOST") and os.getenv("ALERT_SMTP_USER")),
        "webhook_configured": bool(os.getenv("ALERT_WEBHOOK_URL")),
    }