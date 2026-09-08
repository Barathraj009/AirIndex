"""
AirIndex India — MoSPI CPI Transport Data Adapter
===================================================
Fetches Consumer Price Index (CPI) transport-related data from
India's Ministry of Statistics and Programme Implementation (MoSPI)
via the official mospi-esankhyiki Python library.

CPI Transport Division (07) includes:
- Fuel prices (petrol, diesel, CNG) - directly affect airfare
- Rail fare, bus fare, taxi fare - comparison benchmarks

Data source: https://esankhyiki.mospi.gov.in
Python library: pip install mospi-esankhyiki
"""

from __future__ import annotations

import hashlib
import logging
import warnings
from datetime import date, datetime
from typing import Optional

import pandas as pd

from ingestion.adapters.base import BaseSourceAdapter, CollectionRequest, SourceUnavailableError

logger = logging.getLogger(__name__)
warnings.filterwarnings('ignore')


class MospiCpiAdapter(BaseSourceAdapter):
    """Fetches CPI transport indices from MoSPI using the official Python library."""

    source_name = "MOSPI_CPI"
    source_type = "PUBLIC_DATASET"

    # CPI Transport Division = 07
    # Key items for airfare benchmarking:
    TRANSPORT_DIVISION = "Transport"
    FUEL_ITEMS = ["Petrol", "Diesel", "CNG", "Other natural gas (CNG)"]
    FARE_ITEMS = ["Rail fare", "Bus/tram fare", "Taxi fare"]

    # Representative route for mapping CPI to fare observations
    REPRESENTATIVE_ROUTE = ("DEL", "BOM")

    # Pages known to contain transport data (Maharashtra, All India)
    TRANSPORT_PAGES = [100000, 100001, 100002, 100003, 100004, 100005]

    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        """Fetch CPI transport indices from MoSPI."""
        try:
            import esankhyiki
            logger.info("Fetching CPI transport data via mospi-esankhyiki library")

            all_records = []

            # Fetch transport division data from known pages
            for page in self.TRANSPORT_PAGES:
                try:
                    data = esankhyiki.get_data(
                        'CPI',
                        filters={
                            'base_year': '2024',
                            'series': 'Current',
                            'page': str(page)
                        },
                        format='df'
                    )

                    if hasattr(data, 'head') and not data.empty:
                        # Filter for transport division and Combined sector
                        transport_data = data[
                            (data['division'] == self.TRANSPORT_DIVISION) &
                            (data['sector'] == 'Combined')
                        ]

                        for _, row in transport_data.iterrows():
                            item_name = str(row.get('item', ''))
                            code = str(row.get('code', ''))

                            # Only include relevant items
                            if self._is_relevant_item(item_name, code):
                                record = self._create_record(
                                    item_name=item_name,
                                    group=str(row.get('group', '')),
                                    sub_class=str(row.get('sub_class', '')),
                                    cpi_index=float(row.get('index', 100)),
                                    inflation=float(row.get('inflation', 0) or 0),
                                    month=str(row.get('month', '')),
                                    year=str(row.get('year', '')),
                                )
                                all_records.append(record)

                except Exception as e:
                    logger.debug(f"Page {page}: {e}")
                    continue

            if all_records:
                df = pd.DataFrame(all_records)
                logger.info(f"Collected {len(df)} CPI transport records")
                return df

            raise SourceUnavailableError(
                self.source_name,
                "No CPI transport data found in MoSPI"
            )

        except ImportError:
            raise SourceUnavailableError(
                self.source_name,
                "mospi-esankhyiki library not installed"
            )
        except SourceUnavailableError:
            raise
        except Exception as e:
            raise SourceUnavailableError(
                self.source_name,
                f"Error fetching MoSPI data: {e}"
            )

    def _is_relevant_item(self, item_name: str, code: str) -> bool:
        """Check if a CPI item is relevant for airfare benchmarking."""
        name_lower = item_name.lower()

        # Fuel prices directly affect airfare
        if any(fuel in name_lower for fuel in ['petrol', 'diesel', 'cng', 'natural gas']):
            return True

        # Rail/bus/taxi fares as comparison benchmarks
        if any(fare in name_lower for fare in ['rail fare', 'bus', 'taxi', 'tram']):
            return True

        return False

    def _create_record(self, item_name: str, group: str, sub_class: str,
                       cpi_index: float, inflation: float,
                       month: str, year: str) -> dict:
        """Create a fare observation record from CPI data."""
        origin, destination = self.REPRESENTATIVE_ROUTE
        now = datetime.utcnow()

        # Map CPI item to our fare model
        # Fuel prices: CPI index * 10 ≈ approximate fuel cost component
        # Fare items: CPI index * 50 ≈ approximate fare in INR
        if 'fare' in item_name.lower():
            scaled_fare = cpi_index * 50  # Fare benchmark
        else:
            scaled_fare = cpi_index * 10  # Fuel cost component

        # Parse month/year
        try:
            month_num = self._parse_month(month)
            year_num = int(year) if year and year.isdigit() else 2026
            travel_date = date(year_num, month_num, 15)
        except (ValueError, TypeError):
            travel_date = date.today()

        # Determine airline/category based on item type
        if 'petrol' in item_name.lower() or 'diesel' in item_name.lower():
            airline = "FUEL_COST"
        elif 'cng' in item_name.lower() or 'natural gas' in item_name.lower():
            airline = "FUEL_CNG"
        elif 'rail' in item_name.lower():
            airline = "RAIL_BENCHMARK"
        elif 'bus' in item_name.lower() or 'tram' in item_name.lower():
            airline = "BUS_BENCHMARK"
        elif 'taxi' in item_name.lower():
            airline = "TAXI_BENCHMARK"
        else:
            airline = "CPI_TRANSPORT"

        return {
            "origin": origin,
            "destination": destination,
            "airline": airline,
            "flight_number": f"CPI{hashlib.md5(item_name.encode()).hexdigest()[:4].upper()}",
            "travel_date": travel_date.isoformat(),
            "collection_timestamp": now.isoformat(),
            "booking_window_days": 30,
            "fare_class": "CPI_BENCHMARK",
            "base_fare": scaled_fare * 0.72,
            "taxes_fees": scaled_fare * 0.28,
            "total_fare": scaled_fare,
            "currency": "INR",
            "availability_status": "AVAILABLE",
            "source": self.source_name,
            "source_type": self.source_type,
            "data_quality_status": "VALID",
            "quality_flags": f"cpi_index={cpi_index};inflation={inflation};item={item_name}",
        }

    def _parse_month(self, month_str: str) -> int:
        """Parse month string to month number."""
        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        return month_map.get(month_str.lower().strip(), 1)

    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Map CPI data to the canonical fare observation schema."""
        if raw_df.empty:
            return pd.DataFrame()
        return raw_df
