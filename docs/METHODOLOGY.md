# APIx Methodology — v1.0.0

**Modified Laspeyres Route-Weighted Airfare Price Index**

## 1. Representative fare per route per period

For route *r* in period *t*, and for each observed booking window
*w* ∈ {T+1, T+7, T+15, T+30, T+45}, the representative fare is the
**median** of `total_fare` across all `VALID` (or `VALID`+`SUSPICIOUS`
if configured) observations for that (route, window, period) cell.
Median rather than mean is used because airfare distributions are
right-skewed and median is materially more robust to any outliers that
slip past the IQR/MAD screen.

The route-level representative fare for the period is then the
configured booking-window-weighted average of those per-window medians
(default: equal weight across whatever windows were actually observed
that period; administrators can set explicit weights, e.g. more weight
on T+7/T+15 to reflect typical traveller booking behaviour).

## 2. Price relative

For each route: `relative_r = fare_r,t / fare_r,base`.

## 3. Index value

```
APIx_t = 100 × Σ_r ( w_r × relative_r )
```

where `w_r` are the configured route basket weights (renormalized to
sum to 1.0 across whichever routes had data in *both* the base and
current period — see "Missing data handling" below).

## 4. Route contribution

```
contribution_r = w_r × (relative_r − 1) × 100
```

Contributions sum to approximately `APIx_t − 100`.

## 5. Airline contribution

Computed as a transparent proxy: within the current period, each
airline is weighted by its observed share of valid observations, and
its own median-fare relative (current vs base) is computed the same way
as the route-level relative. This is disclosed as a proxy, not a claim
of true market-share weighting (which would require external traffic
data the platform doesn't have).

## 6. Missing data handling

If a configured route has no valid observations in the base period, the
current period, or both, it is excluded from that period's calculation
and reported in `routes_missing_data`. The remaining routes' weights are
renormalized (divided by the sum of the weights of routes that *do*
have data) so the index remains defined. This is disclosed in every
result's `calculation_breakdown` field — nothing is silently dropped.

## 7. Reproducibility

The engine is a pure function of `(observations_df, IndexConfig,
as_of_period)` — no randomness, no wall-clock reads during calculation,
deterministic pandas/numpy aggregation. Identical inputs always produce
identical output; this is enforced by an explicit unit test
(`tests/test_index_engine.py::test_reproducibility`).

## 8. Configurability

Base period, route weights, booking-window weights, and whether
`SUSPICIOUS`-flagged observations are included are all fields on
`IndexConfig` — none of this is hardcoded, and (once the admin API in
Phase 3 exists) will be editable by ADMIN users without a code change,
per spec section 4/10.

## Known limitation / area for review

The route weights currently shipped in `demo_data_generator.ROUTE_BASKET`
are **illustrative**, loosely proportional to approximate trunk-route
traffic share — they are not official MoSPI/DGCA passenger-traffic
weights. Before any real presentation of index *levels* as
policy-relevant, the team should source actual route-level traffic
share data (DGCA publishes domestic sector-wise passenger data at
https://www.dgca.gov.in — see "आंकड़े और रिपोर्ट" → "घरेलू विमान परिवहन" →
"मासिक आंकड़े") to calibrate `route_weights` properly. That specific
deep-linked page turned out to be a JS-driven portal that doesn't
resolve to a data table via a plain HTTP fetch — it needs interactive
navigation, which wasn't accessible in this build session. The
*methodology* (steps 1–7 above) is independent of which specific
weights are plugged in.

Airline-level weighting is **not** on the same footing: `AIRLINES` in
`demo_data_generator.py` now uses real, cited August 2026 DGCA domestic
market share (IndiGo 64.2%, Air India Group 27.3%, Akasa Air 5.4%,
SpiceJet 2%, per DGCA's monthly traffic report as covered by Deccan
Herald), so the demo data's airline mix is grounded in a real reported
number, not a guess. The Air India / Air India Express split within
the 27.3% group figure is still an estimate, since the source found
reports the group combined.

## Real reference data point for backtesting

One real, citable data point was found during this build: per DGCA
data reported to the Rajya Sabha (Minister of State for Civil Aviation
Murlidhar Mohol, per Millennium Post's coverage, July 2026), **average
domestic airfare rose approximately 20.5% across 72 domestic routes,
comparing June 2026 to March 2025.** The underlying 72 routes weren't
disclosed in that reply, and this is a single two-point aggregate
comparison rather than a monthly time series — it's not enough on its
own to populate a meaningful `DGCA_MONTHLY_AVG` reference series (that
would require the actual monthly average-fare figures DGCA holds
internally, not just this one aggregate comparison), so
`ReferenceDataPoint` rows for `DGCA_MONTHLY_AVG` are still empty by
design rather than backfilled with an invented monthly path. This one
real figure is at least a plausible sanity check: whatever the
backtesting page eventually loads as real DGCA data, a ~20% rise over
that 15-month window is the ballpark to expect.
