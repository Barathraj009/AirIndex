"""
CPI Airfare Index — stores MoSPI published CPI data directly.

This is the PRIMARY data source for the Airfare Price Index.
The MoSPI CPI code 07.3.3.1 (Passenger transport by air, domestic)
IS the official airfare price index for India.

Base year: 2024=100
Source: https://esankhyiki.mospi.gov.in
"""

from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from sqlalchemy.orm import relationship

from app.models.base import Base


class CpiAirfareIndex(Base):
    """Monthly CPI airfare index values from MoSPI."""
    __tablename__ = "cpi_airfare_index"

    id = Column(Integer, primary_key=True)

    # Time dimension
    period = Column(String(7), nullable=False, unique=True, index=True)  # YYYY-MM
    data_date = Column(Date, nullable=False)  # 15th of the month (mid-month reference)

    # Core CPI values (base 2024=100)
    airfare_index = Column(Float, nullable=False)  # Code 07.3.3.1
    transport_index = Column(Float, nullable=True)  # Code 07 (division)
    general_index = Column(Float, nullable=True)  # Code 00 (all items)

    # Inflation metrics
    inflation_yoy = Column(Float, nullable=True)  # Year-over-year %
    inflation_mom = Column(Float, nullable=True)  # Month-over-month %

    # Metadata
    source = Column(String(50), default="MOSPI_CPI")
    source_url = Column(String(200), default="https://esankhyiki.mospi.gov.in")
    cpi_code = Column(String(20), default="07.3.3.1")
    base_year = Column(String(10), default="2024=100")

    # Audit
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<CpiAirfareIndex {self.period}: index={self.airfare_index}, inflation={self.inflation_yoy}%>"
