"""SQLAlchemy engine + session factory. Not import-verified in this
sandbox (SQLAlchemy isn't installed here) — see
docs/VERIFICATION_LOG.md for what actually was verified (the equivalent
schema design against SQLite in tests/test_db_schema.py)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
