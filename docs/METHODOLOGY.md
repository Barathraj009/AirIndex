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

The route weights currently shipped in
`app.services.route_basket.ROUTE_BASKET` are **proportional to
approximate all-India domestic trunk-route traffic share** — they are
not official passenger-traffic weights. Before any real
presentation of index *levels* as policy-relevant, the team should
source actual route-level traffic share data to calibrate
`route_weights` properly. The *methodology* (steps 1–7 above) is
independent of which specific weights are plugged in, and ADMIN users
can override weights via the routes table/API without a code change.

Airline-level contribution is computed from the **observed live fare
data itself** (each airline weighted by its share of valid
observations in the current period, as disclosed in section 5) — it is
a transparent proxy and never presented as true market-share weighting.
