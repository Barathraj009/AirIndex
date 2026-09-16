"""Scraper health/status service — the "health report" for the web-scraping
framework. Merges:
  1. the static source registry (ingestion/scrapers/sources.py) — the
     honest LIVE / DEMO / MOCK / UNAVAILABLE status per source;
  2. the live DB state (data_sources / ingestion_runs / scraper_errors) —
     last run outcome, last success, last failure reason;
  3. a fresh (fail-closed, forced) robots.txt verdict when requested so the
     Scraper Monitor can show whether a source's robots.txt has changed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ingestion.scrapers.robots import RobotsVerdict
from ingestion.scrapers.sources import SOURCE_REGISTRY, ScraperSpec, SourceStatus


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# DataSource name of the licensed (RapidAPI) Google Flights fare feed — the
# platform's only real-time live source. Surfaced separately from the
# crawler registry because it is an API feed, not a scraped website.
LIVE_FEED_SOURCE_NAME = "GOOGLE_FLIGHTS_API"


def live_feed_status_payload(db: Session) -> dict | None:
    """Status payload for the licensed Google Flights feed (single exit point
    for the Scraper Monitor / Dashboard strip). Mirrors crawl sources but is
    computed purely from the data_sources row + last ingestion run."""
    from app.models.reference import DataSource

    ds = db.query(DataSource).filter(DataSource.name == LIVE_FEED_SOURCE_NAME).first()
    if ds is None:
        return None

    if ds.last_failure_reason:
        status, reason = "UNAVAILABLE", ds.last_failure_reason
    elif ds.last_success_at:
        status, reason = "LIVE", None
    else:
        status, reason = "UNAVAILABLE", "Feed configured but no successful collection yet"

    return {
        "source_name": LIVE_FEED_SOURCE_NAME,
        "label": "Google Flights (RapidAPI)",
        "category": "FEED",
        "base_url": "https://google-flights8.p.rapidapi.com",
        "status": status,
        "reason": reason,
        "last_run_status": "SUCCESS" if ds.last_success_at else
        ("FAILED" if ds.last_failure_reason else "NEVER_RUN"),
        "last_success_at": ds.last_success_at.isoformat() if ds.last_success_at else None,
        "last_failure_reason": ds.last_failure_reason,
        "as_of": _utcnow_iso(),
    }


def source_status_payload(spec: ScraperSpec, db: Session, rows: dict,
                          robots: RobotsVerdict | None = None) -> dict:
    last_run = rows.get(spec.source_name, {})
    return {
        "source_name": spec.source_name,
        "label": spec.label,
        "category": spec.category,
        "base_url": spec.base_url,
        "robots_url": spec.robots_url,
        "status": spec.status,
        "reason": spec.reason,
        "fare_search_path": spec.fare_search_path,
        "demo_fallback": spec.demo_fallback,
        "notes": spec.notes,
        "robots_check": robots.as_dict() if robots else None,
        "last_run_status": last_run.get("status"),
        "last_run_at": last_run.get("started_at"),
        "last_success_at": last_run.get("last_success_at"),
        "last_failure_reason": last_run.get("last_failure_reason"),
        "as_of": _utcnow_iso(),
    }


def build_status_summary(specs: list[ScraperSpec], db: Session,
                         include_robot_checks: bool = False,
                         force_robot_checks: bool = False,
                         robots_policy=None) -> dict:
    """Build the merged status payload for all registered web sources.

    `force_robot_checks=True` performs a live, cache-bypassing robots.txt
    fetch for each source (network). Default: NO network — status comes
    from the registry plus DB run state, and (optionally) the cached
    robots verdict if one exists in `robots_policy`.
    """
    if robots_policy is None:
        from ingestion.scrapers.robots import GLOBAL_ROBOTS_POLICY
        robots_policy = GLOBAL_ROBOTS_POLICY

    # Per-source last-run info from data_sources (cheap single query).
    from app.models.reference import DataSource

    src_rows = {s.name: s for s in db.query(DataSource).all()}
    last_runs = {}
    for name, ds in src_rows.items():
        if ds.last_failure_reason:
            state = "UNAVAILABLE"
        elif ds.last_success_at:
            state = "SUCCESS"
        else:
            state = "NEVER_RUN"
        last_runs[name] = {
            "status": state,
            "started_at": ds.last_success_at,
            "last_success_at": ds.last_success_at.isoformat() if ds.last_success_at else None,
            "last_failure_reason": ds.last_failure_reason,
        }

    items = []
    for spec in specs:
        robots = None
        if include_robot_checks:
            if spec.fare_search_path:
                robots = robots_policy.check(spec.base_url, spec.fare_search_path, force=force_robot_checks)
        items.append(source_status_payload(spec, db, last_runs, robots))

    counts = {}
    for spec in specs:
        counts[spec.status] = counts.get(spec.status, 0) + 1

    return {
        "sources": items,
        "summary": {
            "total": len(specs),
            "by_status": {k: counts.get(k, 0) for k in (SourceStatus.LIVE, SourceStatus.DEMO,
                                                        SourceStatus.MOCK, SourceStatus.UNAVAILABLE)},
        },
        "live_feeds": [p for p in (live_feed_status_payload(db),) if p is not None],
        "as_of": _utcnow_iso(),
    }