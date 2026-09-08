import { Link } from 'react-router-dom'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, StatCard, Card, LoadingState, ErrorState } from '../components/ui'
import type { DashboardSummary, DataQualitySummary } from '../types'

export default function Overview() {
  const summary = useApiQuery<DashboardSummary>('/dashboard/summary')
  const quality = useApiQuery<DataQualitySummary>('/data-quality/summary')

  if (summary.loading) return <LoadingState label="Loading dashboard…" />
  if (summary.error) return <ErrorState message={summary.error} />
  if (!summary.data) return null

  const { index, n_routes_tracked, n_airlines_tracked, current_period, base_period } = summary.data

  const topContributors = Object.entries(index.route_contributions)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 6)

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle={`Airfare Price Index snapshot — base ${base_period}, current period ${current_period}`}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Current APIx" value={index.index_value.toFixed(2)} sub={`Base = 100.0`} />
        <StatCard
          label="Change vs base"
          value={`${index.change_from_base_pct >= 0 ? '+' : ''}${index.change_from_base_pct.toFixed(2)}%`}
          tone={index.change_from_base_pct >= 0 ? 'up' : 'down'}
          sub={`as of ${index.as_of_period}`}
        />
        <StatCard label="Routes tracked" value={n_routes_tracked} sub={`${index.n_observations_used.toLocaleString()} obs. used`} />
        <StatCard label="Airlines tracked" value={n_airlines_tracked} sub={index.methodology_version} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Top route contributors to index change" className="lg:col-span-2">
          <div className="space-y-2">
            {topContributors.map(([route, val]) => (
              <div key={route} className="flex items-center gap-3 text-sm">
                <div className="w-20 font-medium">{route}</div>
                <div className="flex-1 h-3 bg-slate-100 rounded relative overflow-hidden">
                  <div
                    className={`absolute h-3 ${val >= 0 ? 'bg-red-500' : 'bg-emerald-500'}`}
                    style={{
                      width: `${Math.min(100, Math.abs(val) * 20)}%`,
                      left: val >= 0 ? '50%' : undefined,
                      right: val < 0 ? '50%' : undefined,
                    }}
                  />
                </div>
                <div className={`w-16 text-right ${val >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                  {val.toFixed(3)}
                </div>
              </div>
            ))}
          </div>
          <Link to="/routes" className="text-xs text-blue-600 mt-3 inline-block">
            View full route analysis →
          </Link>
        </Card>

        <Card title="Data quality snapshot">
          {quality.data ? (
            <div className="space-y-2 text-sm">
              <Row label="Valid" value={quality.data.valid} tone="text-emerald-600" />
              <Row label="Suspicious" value={quality.data.suspicious} tone="text-amber-600" />
              <Row label="Invalid" value={quality.data.invalid} tone="text-red-600" />
              <Row label="Unavailable" value={quality.data.unavailable} tone="text-slate-500" />
              <div className="pt-2 text-xs text-muted">{quality.data.valid_pct}% of rows valid</div>
              <Link to="/quality" className="text-xs text-blue-600 inline-block pt-1">
                View data quality detail →
              </Link>
            </div>
          ) : (
            <LoadingState />
          )}
        </Card>
      </div>

      <div className="mt-4">
        <Card title="Methodology">
          <p className="text-sm text-slate-600">
            APIx is a modified Laspeyres route-weighted index. See the{' '}
            <Link to="/methodology" className="text-blue-600">
              full methodology page
            </Link>{' '}
            for the formula, weighting, and known limitations.
          </p>
        </Card>
      </div>
    </div>
  )
}

function Row({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className={`font-semibold ${tone}`}>{value.toLocaleString()}</span>
    </div>
  )
}
