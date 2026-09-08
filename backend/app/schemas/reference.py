from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class RouteOut(BaseModel):
    id: int
    origin: str
    destination: str
    weight: float
    distance_tier: Optional[str]
    active: bool

    model_config = {"from_attributes": True}


class RouteIn(BaseModel):
    origin: str
    destination: str
    weight: float
    distance_tier: Optional[str] = None
    active: bool = True


class RouteWeightUpdate(BaseModel):
    weight: float


class AirlineOut(BaseModel):
    id: int
    name: str
    iata_code: Optional[str]
    active: bool

    model_config = {"from_attributes": True}


class FareObservationOut(BaseModel):
    id: int
    origin: str
    destination: str
    airline: str
    flight_number: Optional[str]
    travel_date: date
    collection_timestamp: datetime
    booking_window_days: Optional[int]
    total_fare: Optional[float]
    availability_status: str
    source: str
    source_type: str
    data_quality_status: str
    quality_flags: Optional[str]

    model_config = {"from_attributes": True}


class DataQualitySummaryOut(BaseModel):
    total_rows: int
    valid: int
    suspicious: int
    invalid: int
    unavailable: int
    duplicates_removed: int
    outliers_iqr: int
    outliers_mad: int
    valid_pct: float
    issues_sample: list[str]


class IngestionRunOut(BaseModel):
    id: int
    data_source_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    rows_collected: int
    rows_valid: int
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class TriggerIngestionRequest(BaseModel):
    source_names: Optional[list[str]] = None  # None = all active sources


class BacktestRequest(BaseModel):
    start_period: str
    end_period: str
    reference_dataset: str = "DGCA_MONTHLY_AVG"  # or "DEMO_REFERENCE"


class BacktestResultOut(BaseModel):
    start_period: str
    end_period: str
    reference_dataset: str
    mae: Optional[float]
    rmse: Optional[float]
    mape: Optional[float]
    correlation: Optional[float]
    points: list[dict]
    reference_available: bool
    note: Optional[str] = None
