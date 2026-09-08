"""Reference data for backtesting (spec section 8). `dataset_name`
distinguishes a real sourced dataset (e.g. "DGCA_MONTHLY_AVG", to be
populated by the SIH team from DGCA publications) from the
explicitly-labelled "DEMO_REFERENCE" used for demonstration. The
backtesting router refuses to compare against anything not present in
this table — see app/services/backtesting.run_backtest's
`reference_available` handling."""

from sqlalchemy import Column, Integer, String, Float

from app.models.base import Base


class ReferenceDataPoint(Base):
    __tablename__ = "reference_data_points"

    id = Column(Integer, primary_key=True)
    dataset_name = Column(String(50), nullable=False, index=True)  # "DGCA_MONTHLY_AVG" | "DEMO_REFERENCE"
    period = Column(String(7), nullable=False)  # "YYYY-MM"
    value = Column(Float, nullable=False)
    label = Column(String(100), nullable=True)  # e.g. route or "ALL_INDIA_AVG"
