"""Surge alert notification service for AirIndex India.

Monitors the airfare price index and triggers notifications when
configured thresholds are exceeded. Supports two notification channels:
- Email (SMTP)
- Webhook URLs

Usage:
    from app.services.alerts import check_alert
    result = check_alert()  # returns dict with triggered, message, index_value
"""

from __future__ import annotations

import os
import smtplib
import json
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine, SessionLocal
from app.models.index import IndexRun, IndexConfigModel
from app.models.reference import Route
from app.services.index_engine import IndexConfig, compute_index
from app.api.query_helpers import load_observations_df


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_ALERT_THRESHOLD_PCT = float(os.getenv("ALERT_THRESHOLD_PCT", "10.0"))
ALERT_COOLDOWN_HOURS = int(os.getenv("ALERT_COOLDOWN_HOURS", "24"))
ALERT_ENABLED = os.getenv("ALERT_ENABLED", "True").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_latest_index(db: Session) -> tuple[float, str, str | None]:
    """Compute the current index value and return (value, period, base_period)."""
    config = db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first()
    if not config:
        return 0.0, "N/A", "N/A"

    df = load_observations_df(db)
    if df.empty:
        return 0.0, "N/A", "N/A"

    period_label = sorted(df["travel_date"].str[:7].unique())[-1]
    route_weights = {r.route_key: r.weight for r in db.query(Route).filter(Route.active == True).all()}
    ice_config = IndexConfig(
        base_period=config.base_period,
        route_weights=route_weights,
        booking_window_weights=config.booking_window_weights or None,
        include_suspicious=config.include_suspicious,
    )
    result = compute_index(df, ice_config, as_of_period=period_label)
    return result.index_value, period_label, config.base_period


# ---------------------------------------------------------------------------
# Core alert check
# ---------------------------------------------------------------------------

def check_alert() -> dict:
    """Check whether the airfare price index has crossed the configured threshold.

    Returns a dict with keys:
    - triggered: bool
    - message: str
    - index_value: float
    - base_index_value: float | None
    - change_pct: float | None
    """
    db = SessionLocal()
    try:
        config = db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first()
        if not config:
            return {
                "triggered": False,
                "message": "No active index configuration found.",
                "index_value": 0.0,
                "base_index_value": None,
                "change_pct": None,
            }

        current_index, as_of_period, base_period = _compute_latest_index(db)

        # Get the most recent IndexRun to use as baseline
        previous_run = db.query(IndexRun).filter_by(index_config_id=config.id).order_by(IndexRun.computed_at.desc()).first()
        base_index_value = None
        change_pct = None

        if previous_run and previous_run.index_value is not None:
            base_index_value = previous_run.index_value
            if base_index_value != 0:
                change_pct = round((current_index - base_index_value) / base_index_value * 100, 2)
        else:
            change_pct = None

        triggered = False
        message = ""

        if ALERT_ENABLED and change_pct is not None and abs(change_pct) >= DEFAULT_ALERT_THRESHOLD_PCT:
            triggered = True
            direction = "increased" if change_pct > 0 else "decreased"
            message = (
                f"Airfare index {direction} by {abs(change_pct):.2f}% "
                f"(from {base_index_value:.2f} to {current_index:.2f}; "
                f"as-of period: {as_of_period}, base period: {base_period})"
            )
        elif not ALERT_ENABLED:
            message = "Alerts are currently disabled via ALERT_ENABLED setting."
        else:
            message = (
                f"Airfare index changed by {change_pct:.2f}% (threshold: {DEFAULT_ALERT_THRESHOLD_PCT:.0f}%), "
                f"but did not cross the threshold. Current: {current_index:.2f}, "
                f"Base: {base_index_value:.2f}"
            )

        return {
            "triggered": triggered,
            "message": message,
            "index_value": current_index,
            "base_index_value": base_index_value,
            "change_pct": change_pct,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Email notification
# ---------------------------------------------------------------------------

def _send_email_alert(subject: str, body: str) -> bool:
    smtp_host = os.getenv("ALERT_SMTP_HOST")
    smtp_port = int(os.getenv("ALERT_SMTP_PORT", "587"))
    smtp_user = os.getenv("ALERT_SMTP_USER")
    smtp_password = os.getenv("ALERT_SMTP_PASSWORD")
    from_email = os.getenv("ALERT_FROM_EMAIL", "airindex-alerts@example.com")

    if not all([smtp_host, smtp_user, smtp_password]):
        return False

    recipients = [e.strip() for e in os.getenv("ALERT_TO_EMAILS", "").split(",") if e.strip()]
    if not recipients:
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Webhook notification
# ---------------------------------------------------------------------------

def _send_webhook_alert(webhook_url: str, payload: dict) -> bool:
    if not webhook_url:
        return False
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status < 400
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API: check and notify
# ---------------------------------------------------------------------------

def check_and_notify() -> dict:
    """Check the index and send notifications through configured channels."""
    result = check_alert()
    if not result["triggered"]:
        return result

    payload = {
        "alert_type": "airfare_index_change",
        "index_value": result["index_value"],
        "change_pct": result["change_pct"],
        "base_index_value": result["base_index_value"],
        "as_of_period": result.get("as_of_period", "N/A"),
        "base_period": result.get("base_period", "N/A"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if ALERT_ENABLED:
        direction = "increased" if result["change_pct"] > 0 else "decreased"
        _send_email_alert(
            subject=f"AirIndex Alert: Index {direction} by {abs(result['change_pct']):.2f}%",
            body=result["message"],
        )

    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if webhook_url:
        _send_webhook_alert(webhook_url, payload)

    return result