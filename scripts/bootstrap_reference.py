"""
Bootstrap — seeds ONLY reference data needed for the app to run:
routes, the MoSPI data source, default admin user, and an active index
configuration.

NO synthetic/demo fare observations are loaded. The CPI airfare index
table is populated at server startup by the lifespan hook in main.py
(fetching live data from api.mospi.gov.in).

Usage:
    PYTHONPATH=./backend python scripts/bootstrap_reference.py

Environment:
    DATABASE_URL      - Postgres connection string
    SEED_ADMIN_EMAIL  - admin email (default admin@airindex.gov.in)
    SEED_ADMIN_PASSWORD - admin password (required in production)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.services.data_processing import CANONICAL_COLUMNS  # noqa: F401 (schema surface)
from app.models import Base, Route, DataSource, User, IndexConfigModel
from app.services.index_engine import METHODOLOGY_VERSION

# The route basket used by index_engine (weight = share of all-India
# domestic air passenger traffic). These are the routes covered by the
# MoSPI CPI airfare component (07.3.3.1).
ROUTE_BASKET = {
    "DEL-BOM": (0.13, "MEDIUM"),
    "DEL-BLR": (0.11, "MEDIUM"),
    "BOM-BLR": (0.09, "MEDIUM"),
    "DEL-CCU": (0.08, "SHORT"),
    "DEL-HYD": (0.09, "SHORT"),
    "BLR-HYD": (0.07, "SHORT"),
    "DEL-MAA": (0.08, "MEDIUM"),
    "BOM-MAA": (0.07, "MEDIUM"),
    "DEL-GOI": (0.05, "MEDIUM"),
    "BOM-GOI": (0.04, "MEDIUM"),
    "BLR-CCU": (0.04, "LONG"),
    "DEL-TRV": (0.04, "LONG"),
    "BOM-HYD": (0.03, "SHORT"),
    "DEL-PNQ": (0.02, "SHORT"),
    "BLR-MAA": (0.02, "SHORT"),
    "BOM-CCU": (0.02, "LONG"),
}

DATA_SOURCES = [
    ("MOSPI_CPI", "PUBLIC_DATASET"),
]


def bootstrap():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Route).count() == 0:
            for route, (weight, tier) in ROUTE_BASKET.items():
                origin, dest = route.split("-")
                db.add(Route(origin=origin, destination=dest, weight=weight, distance_tier=tier))
            db.commit()
            print(f"Seeded {len(ROUTE_BASKET)} routes.")

        for sname, stype in DATA_SOURCES:
            if db.query(DataSource).filter(DataSource.name == sname).first() is None:
                db.add(DataSource(name=sname, source_type=stype, active=True))
                db.commit()
                print(f"Seeded {sname} data source.")

        admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@airindex.gov.in")
        admin_password = os.getenv("SEED_ADMIN_PASSWORD", "change-me-immediately")

        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            if admin_password in ("change-me-immediately", "analyst123", "viewer123", "", "1234"):
                db.close()
                raise RuntimeError(
                    "Refusing to bootstrap in production with a default admin "
                    "password. Set SEED_ADMIN_PASSWORD to a strong unique value."
                )

        if db.query(User).filter(User.email == admin_email).first() is None:
            db.add(User(email=admin_email, hashed_password=hash_password(admin_password), role="ADMIN"))
            db.commit()
            print(f"Seeded admin user ({admin_email}, ADMIN).")

        if db.query(IndexConfigModel).filter(IndexConfigModel.is_active == True).first() is None:  # noqa: E712
            db.add(IndexConfigModel(
                base_period="2026-01",
                methodology_version=METHODOLOGY_VERSION,
                is_active=True,
                created_by="bootstrap_reference.py",
            ))
            db.commit()
            print("Seeded active index config (base_period=2026-01).")

        db.commit()
        print("Bootstrap complete (no synthetic observations loaded).")
    finally:
        db.close()


if __name__ == "__main__":
    bootstrap()