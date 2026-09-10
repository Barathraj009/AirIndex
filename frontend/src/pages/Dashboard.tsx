import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, StatCard, Card, LoadingState, ErrorState, SourceBadge } from '../components/ui'
import type { DashboardSummary, IndexTrend } from '../types'

export default function Dashboard() {
  const summary = useApiQuery<DashboardSummary>('/dashboard/summary')
  const availablePeriods = useApiQuery<{ periods: string[] }>('/index/available-periods')

  const periodsCsv = useMemo(() => {
    const p = availablePeriods.data?.periods
    return p && p.length > 0 ? p.join(',') : null
  }, [availablePeriods.data])

  const trend = useApiQuery<IndexTrend>(
    periodsCsv ? `/index/trend?periods=${encodeURIComponent(periodsCsv)}` : null,
    [periodsCsv],
  )

  if (summary.loading) return <LoadingState label="Loading dashboard..." />
  if (summary.error) return <ErrorState message={summary.error} />
  if (!summary.data) return null

  const { index, n_routes_tracked, n_airlines_tracked, current_period, base_period } = summary.data

  const topContributors = Object.entries(index.route_contributions)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 8)

  const trendData = (trend.data?.series ?? []).filter((p) => p.index_value !== null)

  const dominantSource = 'PUBLIC_DATASET'

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle={`Base ${base_period}  \u00b7  Current ${current_period}`}
        action={
          <SourceBadge sourceType={dominantSource} />
        }
      />

      <div className="bg-blue-600 text-white rounded-lg px-5 py-4 mb-6">
        <div className="text-xs font-bold uppercase tracking-wide opacity-80 mb-1">Current APIx</div>
        <div className="text-3xl font-bold">{index.index_value.toFixed(2)}</div>
        <div className="text-xs opacity-80 mt-1">
          {index.change_from_base_pct >= 0 ? '+' : ''}{index.change_from_base_pct.toFixed(2)}% from base
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard
          label="Routes tracked"
          value={n_routes_tracked}
          sub={`${index.n_observations_used.toLocaleString()} obs.`}
        />
        <StatCard
          label="Airlines tracked"
          value={n_airlines_tracked}
          sub={index.methodology_version}
        />
        <StatCard
          label="Change vs base"
          value={`${index.change_from_base_pct >= 0 ? '+' : ''}${index.change_from_base_pct.toFixed(2)}%`}
          tone={index.change_from_base_pct >= 0 ? 'up' : 'down'}
          sub={`as of ${index.as_of_period}`}
        />
      </div>

      {trendData.length > 0 && (
        <Card title="Index trend" className="mb-6">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="period" tick={{ fontSize: 11 }} />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="index_value"
                stroke="#1d4ed8"
                strokeWidth={2}
                dot={{ r: 3 }}
                name="APIx"
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Card>
          <h2 className="text-sm font-semibold text-ink mb-1">Route contribution to index</h2>
          <p className="text-[11px] text-muted mb-3">
            How much each route moved the overall index (weighted by basket share).
            <span className="font-medium text-ink"> Contribution = Weight &times; Fare change %</span>.
            All contributions sum to ≈ {index.change_from_base_pct.toFixed(2)}%.
          </p>
          <div className="space-y-2">
            {topContributors.map(([route, val]) => {
              const fare = index.route_fares[route]
              const rawChange = fare ? (fare.relative - 1) * 100 : null
              return (
                <div key={route} className="flex items-center gap-3 text-sm">
                  <div className="w-20 font-medium text-xs">{route}</div>
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
                  <div className="w-40 text-right text-xs">
                    <span className={`font-medium ${val >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                      {val >= 0 ? '+' : ''}{val.toFixed(2)}
                    </span>
                    {rawChange !== null && (
                      <span className="text-muted ml-1.5">
                        ({rawChange >= 0 ? '+' : ''}{rawChange.toFixed(1)}% raw)
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
            {topContributors.length === 0 && (
              <p className="text-xs text-muted">No route contribution data.</p>
            )}
          </div>
        </Card>

        <Card title="Airline snapshot">
          <div className="space-y-2">
            {Object.entries(index.airline_contributions)
              .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
              .slice(0, 6)
              .map(([airline, val]) => (
                <div key={airline} className="flex items-center justify-between text-sm">
                  <span className="font-medium text-xs">{airline}</span>
                  <span className={`text-xs font-medium ${val >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                    {val.toFixed(3)}
                  </span>
                </div>
              ))}
            {Object.keys(index.airline_contributions).length === 0 && (
              <p className="text-xs text-muted">No airline contribution data.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
