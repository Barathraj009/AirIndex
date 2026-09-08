"""Demo/Public-Dataset Adapter — always available, always clearly labelled.

Used so the platform can be demonstrated (dashboard, index calc, data
quality, backtesting) even when no live source is reachable. Never
presented as LIVE data — source_type is DEMO_SIMULATED and every row
carries that label through the entire pipeline into the API responses.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.demo_data_generator import generate_demo_observations  # noqa: E402
from ingestion.adapters.base import BaseSourceAdapter, CollectionRequest  # noqa: E402


class DemoAdapter(BaseSourceAdapter):
    source_name = "DEMO_GENERATOR"
    source_type = "DEMO_SIMULATED"

    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        # Demo generator produces a full multi-month synthetic panel;
        # a real adapter would instead make one bounded request per
        # route/booking-window per the CollectionRequest.
        #
        # Window sizing matters here: a travel month only has *full*
        # booking-window coverage (T+1 through T+45 all represented) once
        # collection dates span from 45 days before that month starts to
        # just before it ends. Too short a collection window leaves edge
        # months with only short-lead (and therefore more expensive)
        # observations, which fakes a fare swing that isn't in the
        # underlying model. Six months of collection history gives
        # several fully-covered months in the middle of the panel for a
        # representative demo snapshot; deliberately-thin edge months are
        # still generated (as any real ingestion history would have) and
        # are filtered out downstream, not hidden.
        start = request.as_of - timedelta(days=150)
        df = generate_demo_observations(start_date=start, n_months=6)
        return df

    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        # generate_demo_observations already emits canonical column names.
        return raw_df
