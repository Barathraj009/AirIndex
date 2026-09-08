import { PageHeader, Card } from '../components/ui'

export default function Methodology() {
  return (
    <div>
      <PageHeader title="Methodology" subtitle="APIx v1.0.0 — Modified Laspeyres Route-Weighted Airfare Price Index" />

      <div className="space-y-4">
        <Card title="1. Representative fare per route per period">
          <p className="text-sm text-slate-700 leading-relaxed">
            For each route and period, the representative fare is the <strong>median</strong> of total fare
            across all VALID observations, aggregated across booking windows using configured (or equal)
            weights. Median is used rather than mean because airfare distributions are right-skewed and
            median is robust to any residual outliers.
          </p>
        </Card>

        <Card title="2–3. Price relative and index value">
          <p className="text-sm text-slate-700 leading-relaxed mb-2">
            For each route: <code className="bg-slate-100 px-1 rounded">relative = fare_current / fare_base</code>.
            The index is the route-weighted mean of price relatives:
          </p>
          <pre className="bg-slate-900 text-slate-100 text-xs rounded p-3 overflow-x-auto">
            APIx_t = 100 × Σ_r ( w_r × relative_r )
          </pre>
        </Card>

        <Card title="4–5. Route and airline contribution">
          <p className="text-sm text-slate-700 leading-relaxed mb-2">
            Route contribution to the index-level change:
          </p>
          <pre className="bg-slate-900 text-slate-100 text-xs rounded p-3 overflow-x-auto mb-2">
            contribution_r = w_r × (relative_r − 1) × 100
          </pre>
          <p className="text-sm text-slate-700 leading-relaxed">
            Airline contribution is a transparent proxy: each airline is weighted by its observed share of
            valid observations in the current period, using the same median-relative calculation restricted
            to that airline's data.
          </p>
        </Card>

        <Card title="6. Missing data handling">
          <p className="text-sm text-slate-700 leading-relaxed">
            If a configured route has no valid observations in the base period, current period, or both, it's
            excluded and reported in <code className="bg-slate-100 px-1 rounded">routes_missing_data</code>.
            Remaining routes' weights are renormalized so the index stays defined — nothing is silently
            dropped; every result's calculation breakdown discloses this.
          </p>
        </Card>

        <Card title="7. Reproducibility">
          <p className="text-sm text-slate-700 leading-relaxed">
            The engine is a pure function of (observations, config, as-of period) — no randomness, no
            wall-clock reads during calculation. Identical inputs always produce identical output, enforced
            by an explicit unit test in the backend test suite.
          </p>
        </Card>

        <Card title="Known limitation">
          <p className="text-sm text-slate-700 leading-relaxed">
            The route weights currently shipped are <strong>illustrative</strong>, loosely proportional to
            approximate trunk-route traffic share — not official MoSPI/DGCA passenger-traffic weights. Before
            presenting index levels as policy-relevant, source actual DGCA route-level traffic share data to
            calibrate route weights. The methodology itself is independent of which weights are plugged in.
          </p>
        </Card>
      </div>
    </div>
  )
}
