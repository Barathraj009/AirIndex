from typing import Optional

from pydantic import BaseModel, Field


class RouteFareDetail(BaseModel):
    base_period_fare: float
    as_of_period_fare: float
    relative: float
    weight: float


class IndexResultOut(BaseModel):
    index_value: float
    base_period: str
    as_of_period: str
    methodology_version: str
    change_from_base_pct: float
    route_contributions: dict[str, float]
    airline_contributions: dict[str, float]
    route_fares: dict[str, RouteFareDetail]
    calculation_breakdown: list[str]
    n_observations_used: int
    routes_missing_data: list[str]


class IndexTrendPoint(BaseModel):
    period: str
    index_value: Optional[float]
    n_observations_used: int


class IndexTrendOut(BaseModel):
    series: list[IndexTrendPoint]
    methodology_version: str


class IndexConfigIn(BaseModel):
    base_period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    route_weights: dict[str, float]
    booking_window_weights: Optional[dict[str, float]] = None
    include_suspicious: bool = False
    notes: Optional[str] = None


class IndexConfigOut(IndexConfigIn):
    id: int
    methodology_version: str
    is_active: bool
    created_by: Optional[str]

    model_config = {"from_attributes": True}
