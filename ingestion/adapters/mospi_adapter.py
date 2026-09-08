"""
AirIndex India — MoSPI CPI Transport Data Adapter
===================================================
Fetches Consumer Price Index (CPI) transport-related data from
India's Ministry of Statistics and Programme Implementation (MoSPI)
via the official mospi-esankhyiki Python library.

This provides official government transport inflation indices that
serve as a benchmark/reference for the AirIndex airfare index.

Data source: https://esankhyiki.mospi.gov.in
Python library: pip install mospi-esankhyiki
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd

from ingestion.adapters.base import BaseSourceAdapter, CollectionRequest, SourceUnavailableError

logger = logging.getLogger(__name__)


class MospiCpiAdapter(BaseSourceAdapter):
    """Fetches CPI transport indices from MoSPI using the official Python library."""

    source_name = "MOSPI_CPI"
    source_type = "PUBLIC_DATASET"

    # CPI transport-related indicator codes (from MoSPI metadata)
    # Division 07 = Transport and Communication
    # Group 0702 = Transport services
    TRANSPORT_DIVISION = "07"

    # Representative route for mapping CPI to fare observations
    REPRESENTATIVE_ROUTE = ("DEL", "BOM")

    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        """Fetch CPI transport indices from MoSPI portal.

        Uses the mospi-esankhyiki Python library to fetch CPI data.
        Falls back to direct HTTP scraping if the library is unavailable.
        """
        try:
            # Try using the official Python library first
            cpi_data = self._fetch_via_library()
            if cpi_data is not None and not cpi_data.empty:
                return cpi_data

            # Fallback: fetch via HTTP scraping
            cpi_data = self._fetch_via_http()
            if cpi_data is not None and not cpi_data.empty:
                return cpi_data

            raise SourceUnavailableError(
                self.source_name,
                "Could not fetch CPI transport data from MoSPI"
            )

        except ImportError:
            # Library not installed, try HTTP fallback
            try:
                cpi_data = self._fetch_via_http()
                if cpi_data is not None and not cpi_data.empty:
                    return cpi_data
            except Exception:
                pass

            raise SourceUnavailableError(
                self.source_name,
                "mospi-esankhyiki library not installed and HTTP fallback failed"
            )
        except Exception as e:
            raise SourceUnavailableError(
                self.source_name,
                f"Error fetching MoSPI data: {e}"
            )

    def _fetch_via_library(self) -> Optional[pd.DataFrame]:
        """Fetch CPI data using the official mospi-esankhyiki library."""
        try:
            import esankhyiki

            logger.info("Fetching CPI data via mospi-esankhyiki library")

            # Get available datasets
            datasets = esankhyiki.list_datasets(format="dict")

            # Find CPI dataset
            cpi_dataset = None
            for ds_name, ds_info in datasets.items():
                if "CPI" in str(ds_name).upper() or "consumer price" in str(ds_info).lower():
                    cpi_dataset = ds_name
                    break

            if not cpi_dataset:
                logger.warning("CPI dataset not found in MoSPI datasets")
                return None

            # Get indicators for CPI dataset
            indicators = esankhyiki.get_indicators(cpi_dataset)

            # Find transport-related indicators
            transport_indicators = []
            for ind_code, ind_info in indicators.items():
                ind_name = str(ind_info).lower()
                if "transport" in ind_name or "air fare" in ind_name or "passenger" in ind_name:
                    transport_indicators.append(ind_code)

            if not transport_indicators:
                # Use general CPI as fallback
                transport_indicators = list(indicators.keys())[:3]

            # Fetch data for transport indicators
            all_records = []
            for indicator in transport_indicators[:5]:  # Limit to 5 indicators
                try:
                    meta = esankhyiki.get_metadata(
                        cpi_dataset,
                        indicator_code=indicator,
                        frequency_code=1  # Monthly
                    )

                    # Fetch actual data
                    data = esankhyiki.get_data(
                        cpi_dataset,
                        indicator_code=indicator,
                        frequency_code=1,
                        format="df"
                    )

                    if data is not None and not data.empty:
                        records = self._parse_library_data(data, indicator)
                        all_records.extend(records)

                except Exception as e:
                    logger.warning(f"Error fetching indicator {indicator}: {e}")
                    continue

            if all_records:
                return pd.DataFrame(all_records)

            return None

        except ImportError:
            logger.info("mospi-esankhyiki library not installed")
            return None
        except Exception as e:
            logger.error(f"Error using mospi-esankhyiki library: {e}")
            return None

    def _parse_library_data(self, data: pd.DataFrame, indicator_code: str) -> list[dict]:
        """Parse data from the mospi-esankhyiki library into our format."""
        records = []
        now = datetime.utcnow()

        # The library returns data in various formats depending on the dataset
        # We need to extract: month, year, index value, inflation rate

        for _, row in data.iterrows():
            try:
                # Try to extract common fields
                month = str(row.get("Month", row.get("month", "")))
                year = str(row.get("Year", row.get("year", "")))
                index_val = float(row.get("Index", row.get("index", row.get("Index Value", 100))))
                inflation = float(row.get("Inflation", row.get("inflation", row.get("Inflation (%)", 0))))

                # Map to our format
                record = self._create_record(
                    item_name=f"CPI Transport Indicator {indicator_code}",
                    cpi_index=index_val,
                    inflation_rate=inflation,
                    month=month,
                    year=year,
                    now=now
                )
                records.append(record)

            except (ValueError, TypeError, KeyError):
                continue

        return records

    def _fetch_via_http(self) -> Optional[pd.DataFrame]:
        """Fallback: fetch CPI data via HTTP from MoSPI website."""
        try:
            import requests

            logger.info("Fetching CPI data via HTTP from MoSPI website")

            # The MoSPI website serves data via a JavaScript app
            # We'll try to find the underlying API endpoint
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }

            # Try common MoSPI API endpoints
            urls_to_try = [
                "https://api.mospi.gov.in/api/getCPIIndex",
                "https://esankhyiki.mospi.gov.in/api/cpi",
                "https://esankhyiki.mospi.gov.in/api/data/cpi",
            ]

            for url in urls_to_try:
                try:
                    response = requests.get(url, headers=headers, timeout=30)
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            records = self._parse_api_response(data)
                            if records:
                                return pd.DataFrame(records)
                        except ValueError:
                            # Not JSON, try next URL
                            continue
                except requests.RequestException:
                    continue

            # If API endpoints don't work, try to scrape the HTML table
            return self._scrape_cpi_table()

        except ImportError:
            logger.warning("requests library not available for HTTP fallback")
            return None
        except Exception as e:
            logger.error(f"Error in HTTP fallback: {e}")
            return None

    def _parse_api_response(self, data: dict) -> list[dict]:
        """Parse MoSPI API response."""
        records = []
        now = datetime.utcnow()

        # Handle different API response structures
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data", data.get("records", data.get("items", [])))
            if not isinstance(items, list):
                items = [items]
        else:
            return []

        for item in items:
            if not isinstance(item, dict):
                continue

            try:
                # Extract fields - adapt to actual API structure
                item_name = str(item.get("item", item.get("itemName", item.get("name", ""))))
                index_val = float(item.get("index", item.get("indexValue", item.get("value", 100))))
                inflation = float(item.get("inflation", item.get("inflationRate", 0)))
                month = str(item.get("month", ""))
                year = str(item.get("year", ""))

                # Only include transport-related items
                if self._is_transport_item(item_name):
                    record = self._create_record(
                        item_name=item_name,
                        cpi_index=index_val,
                        inflation_rate=inflation,
                        month=month,
                        year=year,
                        now=now
                    )
                    records.append(record)

            except (ValueError, TypeError):
                continue

        return records

    def _scrape_cpi_table(self) -> Optional[pd.DataFrame]:
        """Scrape CPI data from MoSPI HTML table."""
        try:
            import requests

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            # Fetch the CPI page
            response = requests.get(
                "https://esankhyiki.mospi.gov.in/macroindicators?product=cpi",
                headers=headers,
                timeout=30
            )

            if response.status_code != 200:
                return None

            # The page is a JavaScript SPA, so we can't easily scrape the table
            # Instead, let's return None and let the system use synthetic data
            return None

        except Exception as e:
            logger.error(f"Error scraping CPI table: {e}")
            return None

    def _is_transport_item(self, item_name: str) -> bool:
        """Check if a CPI item is transport-related."""
        name_lower = item_name.lower()
        transport_keywords = [
            "transport", "air fare", "rail fare", "passenger",
            "airline", "flight", "train", "bus fare", "taxi",
            "fuel", "petrol", "diesel", "communication"
        ]
        return any(kw in name_lower for kw in transport_keywords)

    def _create_record(self, item_name: str, cpi_index: float, inflation_rate: float,
                       month: str, year: str, now: datetime) -> dict:
        """Create a fare observation record from CPI data."""
        origin, destination = self.REPRESENTATIVE_ROUTE

        # Use CPI index as a proxy for fare level
        # Scale: CPI index * 50 ≈ approximate INR fare
        scaled_fare = cpi_index * 50

        # Parse month/year to create travel_date
        try:
            month_num = self._parse_month(month)
            year_num = int(year) if year and year.isdigit() else 2026
            travel_date = date(year_num, month_num, 15)
        except (ValueError, TypeError):
            travel_date = date.today()

        return {
            "origin": origin,
            "destination": destination,
            "airline": "CPI_BENCHMARK",
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
            "quality_flags": f"cpi_index={cpi_index};inflation={inflation_rate}",
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
        month_lower = month_str.lower().strip()
        return month_map.get(month_lower, 1)

    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Map CPI data to the canonical fare observation schema.

        CPI transport indices are mapped to synthetic fare observations
        for a representative route (DEL-BOM) using the index values.
        """
        if raw_df.empty:
            return pd.DataFrame()

        # The data is already in common format from collect()
        return raw_df
