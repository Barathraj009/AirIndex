"""
Base class for the web scrapers in this framework.

Reuses the existing ingestion adapter contract
(ingestion/adapters/base.py: BaseSourceAdapter) so these adapters drop
straight into `ingestion_runner.collect_from_sources()` with zero
core-system changes, and reuses the standard scraper fare model
(ingestion/scrapers/fare_model.py) for the canonical mapping.

Compliance-first behavior:
  * Before ANY collection, the adapter performs a fail-closed robots.txt
    check for the source's fare-search path.
  * If robots.txt disallows the path (or is unreachable), `collect()`
    raises `SourceUnavailableError` with the documented reason — it never
    fabricates data and never tries to bypass anti-bot / CAPTCHA / login.
  * Each concrete scraper implements `_collect_compliant()` for the day a
    compliant live path exists (e.g. a partner/affiliate API). Until then
    every source has status UNAVAILABLE and the adapter honestly reports
    so — see ingestion/scrapers/sources.py for the live findings.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from ingestion.adapters.base import BaseSourceAdapter, CollectionRequest, SourceUnavailableError
from ingestion.scrapers.robots import RobotsTxtPolicy
from ingestion.scrapers.sources import ScraperSpec, SourceStatus

logger = logging.getLogger(__name__)


class BaseWebScraper(BaseSourceAdapter):
    """Compliance-gated adapter for a single web source (airline/OTA)."""

    source_type = "LIVE_SCRAPE"

    def __init__(self, spec: ScraperSpec, robots_policy: Optional[RobotsTxtPolicy] = None,
                 force_robots_check: bool = False):
        self.spec = spec
        self.source_name = spec.source_name
        self.robots_policy = robots_policy or RobotsTxtPolicy()
        self.force_robots_check = force_robots_check

    # ------------------------------------------------------------------
    # compliance gate
    # ------------------------------------------------------------------

    def _robots_verdict(self):
        assert self.spec.fare_search_path is not None, "source has no fare-search path declared"
        return self.robots_policy.check(
            self.spec.base_url, self.spec.fare_search_path, force=self.force_robots_check
        )

    def _compliance_reason(self, verdict) -> str:
        if verdict.allowed:
            return None
        if self.spec.reason:
            return f"{self.spec.reason} ({verdict.reason})"
        return verdict.reason

    def collect(self, request: CollectionRequest) -> pd.DataFrame:
        """Fail-closed compliant entry point. When status is
        UNAVAILABLE/MOCK with an explicit reason we short-circuit before
        any network call unless a force re-check is requested."""
        if not self.force_robots_check and self.spec.status != SourceStatus.DEMO:
            if self.spec.status == SourceStatus.UNAVAILABLE:
                raise SourceUnavailableError(self.spec.source_name, self.spec.reason)
            if self.spec.status == SourceStatus.MOCK:
                raise SourceUnavailableError(self.spec.source_name, "mock source has no live data path")

        verdict = self._robots_verdict()
        compliance_reason = self._compliance_reason(verdict)
        if compliance_reason:
            raise SourceUnavailableError(self.spec.source_name, compliance_reason)

        # Allowed by robots.txt (and not administratively UNAVAILABLE).
        return self._collect_compliant(request)

    def _collect_compliant(self, request: CollectionRequest) -> pd.DataFrame:
        raise NotImplementedError(
            "No compliant live collection path exists for this source yet; "
            "re-raise SourceUnavailableError in subclasses until a "
            "partner/affiliate API or a legally-reviewed flow is wired in."
        )

    # ------------------------------------------------------------------
    # canonical mapping
    # ------------------------------------------------------------------

    def to_common_format(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Map the standard scraper frame onto the pipeline's canonical
        columns (source/source_type provenance set by this instance)."""
        from ingestion.scrapers.fare_model import to_canonical_columns

        return to_canonical_columns(raw_df, source=self.source_name, source_type=self.source_type)

    def run(self, request: CollectionRequest):
        """Reuse the base never-raises wrapper so the orchestrator's
        per-source degradation (SOURCE_UNAVAILABLE) keeps working."""
        return super().run(request)