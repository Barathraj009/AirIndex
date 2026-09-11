"""Import every model here so Alembic's `target_metadata = Base.metadata`
autogenerate picks up the full schema from a single import."""

from app.models.base import Base
from app.models.reference import Route, Airline, DataSource, BookingWindowConfig
from app.models.observations import FareObservation
from app.models.ingestion import IngestionRun
from app.models.index import IndexConfigModel, IndexRun, RouteContribution, AirlineContribution
from app.models.auth import User, AuditLogEntry
from app.models.backtesting import ReferenceDataPoint
from app.models.cpi import CpiAirfareIndex
from app.models.wpi_atf import WpiAtfIndex

__all__ = [
    "Base", "Route", "Airline", "DataSource", "BookingWindowConfig",
    "FareObservation", "IngestionRun",
    "IndexConfigModel", "IndexRun", "RouteContribution", "AirlineContribution",
    "User", "AuditLogEntry", "ReferenceDataPoint", "CpiAirfareIndex", "WpiAtfIndex",
]
