import unittest


class TestCpiEngineRemovedPath(unittest.TestCase):
    """cpi_engine (the WPI-ATF MoSPI CPI augmentation engine) was removed in
    the R2 re-scope. The combined airfare curve is now built by
    app.services.combined_series from the two live sources only."""

    def test_product_uses_combined_series(self):
        from app.services.combined_series import build_combined_series, resolve_base_period
        self.assertTrue(callable(build_combined_series))
        self.assertTrue(callable(resolve_base_period))

    def test_sources_are_the_two_real_ones(self):
        from app.services.replay_data import google_flights_replay, mospi_cpi_replay
        gf = google_flights_replay()
        cpi = mospi_cpi_replay()
        self.assertGreater(len(gf), 0)
        self.assertGreater(len(cpi), 0)
        self.assertEqual({r["source"] for r in gf}, {"GOOGLE_FLIGHTS_API"})
        self.assertEqual({r["source"] for r in cpi}, {"MOSPI_CPI"})


if __name__ == "__main__":
    unittest.main()
