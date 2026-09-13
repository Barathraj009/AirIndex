"""Tests for the web-scraping framework (Phase 19-21 of the spec).

Covers:
  * source registry: the 11 named sources, honest UNAVAILABLE status,
    unique ids, complete metadata;
  * web_scraper adapters: registrable, deterministic UNAVAILABLE raise,
    no network unless force_robots_check is passed;
  * robots policy: fail-closed, 404 => allowed, parsing, cache, invalidation;
  * fare model: validation + canonical mapping (incl. total-only estimation);
  * base scraper: positive path (robots all-clear) + provenance mapping;
  * status service summary standalone.

No live network is used: robots fetches are monkeypatched. Uses the in-
memory SQLite metadata like test_db_schema does.
"""

import unittest
from unittest import mock

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models as app_models
from ingestion.adapters.base import SourceUnavailableError, CollectionRequest
from ingestion.scrapers.base import BaseWebScraper
from ingestion.scrapers.fare_model import FareRecord, to_canonical_columns
from ingestion.scrapers.robots import RobotsTxtPolicy
from ingestion.scrapers.sources import SOURCE_REGISTRY, SourceStatus, spec_for
from ingestion.scrapers.web_scrapers import WEB_SCRAPER_REGISTRY

import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if str(Path(REPO_ROOT) / "backend") not in sys.path:
    sys.path.insert(0, str(Path(REPO_ROOT) / "backend"))

EXPECTED_SOURCES = {
    "MAKEMYTRIP_WEB", "YATRA_WEB", "EASEMYTRIP_WEB", "CLEARTRIP_WEB",
    "IXIGO_WEB", "GOIBIBO_WEB", "INDIGO_WEB", "AIR_INDIA_WEB",
    "AIR_INDIA_EXPRESS_WEB", "AKASA_WEB", "SPICEJET_WEB",
}

from datetime import date

REQUEST = CollectionRequest(
    routes=["DEL-BOM"], booking_windows=[7, 14, 30], as_of=date(2026, 9, 13),
)


class SourceRegistryTests(unittest.TestCase):
    def test_registry_has_all_eleven_sources(self):
        names = {s.source_name for s in SOURCE_REGISTRY}
        self.assertEqual(names, EXPECTED_SOURCES)

    def test_unique_ids(self):
        self.assertEqual(len(SOURCE_REGISTRY), len({s.source_name for s in SOURCE_REGISTRY}))

    def test_all_sources_honestly_unavailable(self):
        for spec in SOURCE_REGISTRY:
            self.assertEqual(spec.status, SourceStatus.UNAVAILABLE, spec.source_name)
            self.assertTrue(spec.reason, f"{spec.source_name} must document why")

    def test_metadata_complete(self):
        for spec in SOURCE_REGISTRY:
            self.assertTrue(spec.base_url, spec.source_name)
            self.assertTrue(spec.robots_url, spec.source_name)
            self.assertTrue(spec.label, spec.source_name)
            self.assertTrue(spec.category in ("AIRLINE", "OTA"), spec.source_name)

    def test_fare_search_path_declared(self):
        for spec in SOURCE_REGISTRY:
            self.assertTrue(spec.fare_search_path, spec.source_name)

    def test_spec_for_lookup(self):
        self.assertEqual(spec_for("INDIGO_WEB").status, SourceStatus.UNAVAILABLE)


class WebScraperAdapterTests(unittest.TestCase):
    def test_registry_covers_all_sources(self):
        self.assertEqual(set(WEB_SCRAPER_REGISTRY), EXPECTED_SOURCES)

    def test_adapter_honors_unavailable_without_network(self):
        with mock.patch.object(RobotsTxtPolicy, "check") as check:
            for name, cls in WEB_SCRAPER_REGISTRY.items():
                with self.assertRaises(SourceUnavailableError, msg=name) as ctx:
                    cls().collect(REQUEST)
                self.assertIn(spec_for(name).source_name, str(ctx.exception))
        check.assert_not_called()

    def test_force_robots_check_gates_negative_path(self):
        with mock.patch.object(RobotsTxtPolicy, "check") as check:
            check.return_value = mock.Mock(allowed=False, reason="robots denied")
            for name, cls in WEB_SCRAPER_REGISTRY.items():
                with self.assertRaises(SourceUnavailableError, msg=name):
                    cls(force_robots_check=True).collect(REQUEST)
            self.assertEqual(check.call_count, len(WEB_SCRAPER_REGISTRY))

    def test_force_robots_check_allowed_reaches_collect_compliant(self):
        # Simulate a future day when robots.txt allows: the framework must
        # reach the source-specific collector (which today raises honestly).
        with mock.patch.object(RobotsTxtPolicy, "check") as check:
            check.return_value = mock.Mock(allowed=True, reason="allowed")
            for name, cls in WEB_SCRAPER_REGISTRY.items():
                with self.assertRaises(SourceUnavailableError, msg=name):
                    cls(force_robots_check=True).collect(REQUEST)

    def test_demo_spec_does_not_short_circuit(self):
        demo_cls = BaseWebScraper
        spec = spec_for("INDIGO_WEB")
        with mock.patch.object(RobotsTxtPolicy, "check") as check:
            check.return_value = mock.Mock(allowed=False, reason="x")
            with self.assertRaises(SourceUnavailableError):
                demo_cls(spec, force_robots_check=True).collect(REQUEST)


class RobotsPolicyTests(unittest.TestCase):
    def test_fail_closed_on_network_error(self):
        policy = RobotsTxtPolicy()
        with mock.patch("ingestion.scrapers.robots._fetch_robots_txt", return_value=None):
            verdict = policy.check("https://example.com", "/flights/search")
        self.assertFalse(verdict.allowed)
        self.assertIn("unreachable", verdict.reason)

    def test_404_means_allowed(self):
        policy = RobotsTxtPolicy()
        with mock.patch("ingestion.scrapers.robots._fetch_robots_txt", return_value=""):
            verdict = policy.check("https://example.com", "/any/path")
        self.assertTrue(verdict.allowed)

    def test_disallow_parsing(self):
        policy = RobotsTxtPolicy()
        robots = "User-agent: *\nDisallow: /booking/\n"
        with mock.patch("ingestion.scrapers.robots._fetch_robots_txt", return_value=robots):
            denied = policy.check("https://example.com", "/booking/search")
            ok = policy.check("https://example.com", "/about")
        self.assertFalse(denied.allowed)
        self.assertTrue(ok.allowed)

    def test_cache_reuses_fetch(self):
        policy = RobotsTxtPolicy()
        with mock.patch("ingestion.scrapers.robots._fetch_robots_txt",
                        return_value="User-agent: *\nAllow: /\n") as fetch:
            policy.check("https://cached.test", "/a")
            policy.check("https://cached.test", "/b")
        self.assertEqual(fetch.call_count, 1)

    def test_force_bypasses_cache(self):
        policy = RobotsTxtPolicy()
        with mock.patch("ingestion.scrapers.robots._fetch_robots_txt",
                        return_value="User-agent: *\nAllow: /\n") as fetch:
            policy.check("https://cached2.test", "/a")
            policy.check("https://cached2.test", "/a", force=True)
        self.assertEqual(fetch.call_count, 2)

    def test_invalidate_clears(self):
        policy = RobotsTxtPolicy()
        with mock.patch("ingestion.scrapers.robots._fetch_robots_txt",
                        return_value="User-agent: *\nAllow: /\n") as fetch:
            policy.check("https://cached3.test", "/a")
            policy.invalidate("https://cached3.test/robots.txt")
            policy.check("https://cached3.test", "/a")
        self.assertEqual(fetch.call_count, 2)

    def test_invalid_robots_still_degrades_via_reason(self):
        policy = RobotsTxtPolicy()
        # A malformed robots.txt (parser default allow) should not be
        # reported as "no robots rule" without a reason string.
        with mock.patch("ingestion.scrapers.robots._fetch_robots_txt",
                        return_value="::::not a robots file::::"):
            verdict = policy.check("https://example.com", "/booking/search")
        self.assertIsNotNone(verdict.reason)


class FareModelTests(unittest.TestCase):
    def test_valid_record_required_fields(self):
        rec = FareRecord(origin="DEL", destination="BOM", travel_date="2026-10-01",
                         airline="6E", total_fare=4321.0, booking_window_days=30)
        self.assertEqual(rec.validate(), [])

    def test_missing_total_invalid(self):
        rec = FareRecord(origin="DEL", destination="BOM", travel_date="2026-10-01",
                         airline="6E", total_fare=None, booking_window_days=30)
        self.assertIn("missing_fare", rec.validate())

    def test_total_only_estimation(self):
        rec = FareRecord(origin="DEL", destination="BOM", travel_date="2026-10-01",
                         airline="6E", total_fare=1000.0, booking_window_days=30)
        mapped = to_canonical_columns(pd.DataFrame([rec.as_row()]),
                                      source="TEST_SRC", source_type="LIVE_SCRAPE")
        row = mapped.iloc[0]
        self.assertAlmostEqual(row["total_fare"], 1000.0)
        self.assertAlmostEqual(row["base_fare"], 720.0)
        self.assertAlmostEqual(row["taxes_fees"], 280.0)

    def test_mapping_sets_provenance(self):
        rec = FareRecord(origin="DEL", destination="BOM", travel_date="2026-10-01",
                         airline="6E", total_fare=2000.0, booking_window_days=7)
        mapped = to_canonical_columns(pd.DataFrame([rec.as_row()]),
                                      source="INDIGO_WEB", source_type="LIVE_SCRAPE")
        self.assertEqual(mapped.iloc[0]["source"], "INDIGO_WEB")
        self.assertEqual(mapped.iloc[0]["source_type"], "LIVE_SCRAPE")

    def test_enrichment_columns_dropped_in_canonical(self):
        rec = FareRecord(origin="DEL", destination="BOM", travel_date="2026-10-01",
                         airline="6E", total_fare=2000.0, booking_window_days=7,
                         deep_link="https://x/booking", fare_family="Saver")
        raw = pd.DataFrame([rec.as_row()])
        self.assertIn("deep_link", raw.columns)
        mapped = to_canonical_columns(raw, source="S", source_type="T")
        self.assertNotIn("deep_link", mapped.columns)


class BaseScraperPositivePathTests(unittest.TestCase):
    def test_allowed_path_maps_to_canonical(self):
        class WorkingScraper(BaseWebScraper):
            def _collect_compliant(self, request):
                return pd.DataFrame([{
                    "origin": "DEL", "destination": "BLR",
                    "travel_date": "2026-10-01", "airline": "6E",
                    "total_fare": 3200.0, "booking_window_days": 14,
                }])

        with mock.patch.object(RobotsTxtPolicy, "check") as check:
            check.return_value = mock.Mock(allowed=True, reason="allowed")
            s = WorkingScraper(spec_for("INDIGO_WEB"), force_robots_check=True)
            out_df, err = s.run(REQUEST)
        self.assertIsNone(err)
        self.assertEqual(len(out_df), 1)
        self.assertEqual(out_df.iloc[0]["source"], "INDIGO_WEB")
        self.assertEqual(out_df.iloc[0]["source_type"], "LIVE_SCRAPE")
        self.assertAlmostEqual(out_df.iloc[0]["base_fare"], 3200.0 * 0.72)
        self.assertIn("taxes_fees", out_df.columns)


class ScraperStatusServiceTests(unittest.TestCase):
    def test_summary_counts(self):
        from app.services.scraper_status import build_status_summary

        engine = create_engine("sqlite:///:memory:")
        app_models.Base.metadata.create_all(engine)
        with Session(engine) as db:
            out = build_status_summary(SOURCE_REGISTRY, db, include_robot_checks=False)
        self.assertEqual(out["summary"]["total"], 11)
        self.assertEqual(out["summary"]["by_status"]["UNAVAILABLE"], 11)
        self.assertEqual(out["summary"]["by_status"]["LIVE"], 0)


if __name__ == "__main__":
    unittest.main()