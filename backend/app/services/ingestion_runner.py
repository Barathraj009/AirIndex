"""Shared ingestion orchestration used by both the manual /api/scraping/trigger
endpoint and the APScheduler-backed scheduled jobs (Phase 4).

Each source adapter's `.run()` either returns data or degrades to
SOURCE UNAVAILABLE — never raises — so one bad source can't crash a
request or a scheduled run (spec section 12).
"""

from datetime import date, datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.json_safe import records_json_safe
from app.models.ingestion import IngestionRun
from app.models.reference import DataSource, Route
from app.models.observations import FareObservation
from app.models.auth import AuditLogEntry
from app.services.data_processing import run_pipeline


ADAPTER_REGISTRY = {}


def _adapter_registry():
    # Late import so this module stays importable in offline/test contexts
    # without the root-level `ingestion` package on sys.path.
    from ingestion.adapters.demo_adapter import DemoAdapter
    from ingestion.adapters.gds_adapter import GdsAdapter
    from ingestion.adapters.metasearch_adapter import MetasearchAdapter
    from ingestion.adapters.base import CollectionRequest

    registry = dict(ADAPTER_REGISTRY)
    registry.setdefault("DEMO_GENERATOR", DemoAdapter)
    registry.setdefault("GOOGLE_FLIGHTS_API", GdsAdapter)
    registry.setdefault("GOOGLE_FLIGHTS", MetasearchAdapter)
    return registry, CollectionRequest


def collect_from_sources(db: Session, source_names: list[str] | None = None,
                         triggered_by: str = "scheduler",
                         run_action: str = "SCHEDULED_INGESTION") -> list[dict]:
    """Run every active (optionally name-filtered) data source once and
    persist results. Returns a list of per-source result dicts. Never raises
    for source failures; individual sources degrade to SOURCE_UNAVAILABLE."""
    registry, CollectionRequest = _adapter_registry()

    sources_q = db.query(DataSource).filter(DataSource.active == True)  # noqa: E712
    if source_names:
        sources_q = sources_q.filter(DataSource.name.in_(source_names))
    sources = sources_q.all()
    if not sources:
        return []

    routes = [r.route_key for r in db.query(Route).filter(Route.active == True).all()]  # noqa: E712
    results = []

    for source in sources:
        run = IngestionRun(data_source_id=source.id, triggered_by=triggered_by, status="RUNNING")
        db.add(run)
        db.commit()
        db.refresh(run)

        adapter_cls = registry.get(source.name)
        if adapter_cls is None:
            run.status = "FAILED"
            run.error_message = f"no_adapter_registered_for_{source.name}"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            results.append({"source": source.name, "status": run.status, "detail": run.error_message})
            continue

        adapter = adapter_cls()
        req = CollectionRequest(routes=routes, booking_windows=[1, 7, 15, 30, 45], as_of=date.today())
        raw_df, err = adapter.run(req)

        if raw_df is None:
            source.last_failure_reason = err
            run.status = "SOURCE_UNAVAILABLE"
            run.error_message = err
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            results.append({"source": source.name, "status": run.status, "detail": err})
            continue

        clean_df, report = run_pipeline(raw_df, source=source.name, source_type=source.source_type)
        rows = clean_df.to_dict("records")
        # Idempotent insert: adapters may be deterministic (fixed RNG
        # seed), so re-runs must not violate the unique observation_id
        # constraint — skip rows already collected.
        payload = records_json_safe([
            {**{k: r[k] for k in r if k in FareObservation.__table__.columns.keys()},
             "ingestion_run_id": run.id} for r in rows
        ])
        inserted = db.execute(
            pg_insert(FareObservation).values(payload)
            .on_conflict_do_nothing(index_elements=[FareObservation.__table__.c.observation_id])
        ).rowcount

        source.last_success_at = datetime.now(timezone.utc)
        run.status = "SUCCESS"
        run.completed_at = datetime.now(timezone.utc)
        run.rows_collected = inserted
        run.rows_valid = report.valid
        run.rows_invalid = report.invalid
        run.rows_suspicious = report.suspicious
        run.rows_unavailable = report.unavailable
        db.add(AuditLogEntry(user_id=None, user_email=triggered_by,
                              action=run_action,
                              entity_type="DataSource",
                              entity_id=str(source.id), details={"rows_collected": inserted}))
        db.commit()
        results.append({"source": source.name, "status": run.status, "rows_collected": inserted})

    return results