"""
WPI ATF (Aviation Turbine Fuel) Index — stores MoSPI published WPI data.

Official Wholesale Price Index series for Aviation Turbine Fuel (ATF),
base year 2022-23 = 100. Used to overlay fuel-cost movements against the
airfare CPI so the platform can show "Fuel-cost vs Airfare".

Source: https://esankhyiki.mospi.gov.in
"""

from sqlalchemy import Column, Integer, String, Float, Date, DateTime

from app.models.base import Base


class WpiAtfIndex(Base):
    """Monthly WPI Atf index values from MoSPI."""
    __tablename__ = "wpi_atf_index"

    id = Column(Integer, primary_key=True)

    # Time dimension
    period = Column(String(7), nullable=False, unique=True, index=True)  # YYYY-MM
    data_date = Column(Date, nullable=False)  # 15th of the month (mid-month reference)

    # Core value (base 2022-23=100)
    atf_index = Column(Float, nullable=False)  # WPI item 1202010004 (ATF)

    # Derived metrics
    inflation_mom = Column(Float, nullable=True)  # Month-over-month %
    inflation_yoy = Column(Float, nullable=True)  # Year-over-year %

    # Metadata
    source = Column(String(50), default="MOSPI_WPI")
    source_url = Column(String(200), default="https://esankhyiki.mospi.gov.in")
    wpi_code = Column(String(20), default="1202010004")
    base_year = Column(String(10), default="2022-23=100")

    # Audit
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<WpiAtfIndex {self.period}: index={self.atf_index}, inflation={self.inflation_yoy}%>"