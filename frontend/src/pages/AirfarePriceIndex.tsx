import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, StatCard, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import type { IndexResult, IndexTrend } from '../types'

export default function AirfarePriceIndex() {
  const periodsQuery = useApiQuery<{ periods: string[] }>('/index/available-periods')
  const periods = periodsQuery.data?.periods ?? []
  const periodsParam = periods.join(',')

  const current = useApiQuery<IndexResult>('/index/current')
  const trend = useApiQuery<IndexTrend>(periodsParam ? `/index/trend?periods=${periodsParam}` : null, [periodsParam])

  const [sortBy, setSortBy] = useState<'contribution' | 'route'>('contribution')

  if (current.loading) return <LoadingState label="Computing index…" />
  if (current.error) return <ErrorState message={current.error} />
  if (!current.data) return null

  const routeRows = Object.entries(current.data.route_fares).sort(([ra, a], [rb, b]) =>
    sortBy === 'route' ? ra.localeCompare(rb) : Math.abs(current.data!.route_contributions[rb] ?? 0) - Math.abs(current.data!.route_contributions[ra] ?? 0),
  )

  return (
    <div>
      <PageHeader
        title="Airfare Price Index (APIx)"
        subtitle={`Methodology ${current.data.methodology_version} · base period ${current.data.base_period}`}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Index value" value={current.data.index_value.toFixed(2)} />
        <StatCard
          label="Change from base"
          value={`${current.data.change_from_base_pct >= 0 ? '+' : ''}${current.data.change_from_base_pct.toFixed(2)}%`}
          tone={current.data.change_from_base_pct >= 0 ? 'up' : 'down'}
        />
        <StatCard label="Observations used" value={current.data.n_observations_used.toLocaleString()} />
        <StatCard
          label="Routes missing data"
          value={current.data.routes_missing_data.length}
          sub={current.data.routes_missing_data.join(', ') || 'none'}
        />
      </div>

      <Card title="Trend" className="mb-6">
        {trend.loading && <LoadingState />}
        {trend.data && trend.data.series.filter((p) => p.index_value !== null).length > 1 ? (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trend.data.series}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="period" tick={{ fontSize: 12 }} />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="index_value" stroke="#1d4ed8" strokeWidth={2} dot={{ r: 3 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState message="Not enough periods with full booking-window coverage yet to plot a trend." />
        )}
      </Card>

      <Card title="Route-level detail" className="mb-6">
        <div className="flex gap-2 mb-3 text-xs">
          <button
            onClick={() => setSortBy('contribution')}
            className={`px-2 py-1 rounded ${sortBy === 'contribution' ? 'bg-blue-100 text-blue-700' : 'text-muted'}`}
          >
            Sort by contribution
          </button>
          <button
            onClick={() => setSortBy('route')}
            className={`px-2 py-1 rounded ${sortBy === 'route' ? 'bg-blue-100 text-blue-700' : 'text-muted'}`}
          >
            Sort by route
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted border-b border-slate-200">
              <th className="py-2">Route</th>
              <th className="py-2 text-right">Weight</th>
              <th className="py-2 text-right">Base fare (₹)</th>
              <th className="py-2 text-right">Current fare (₹)</th>
              <th className="py-2 text-right">Relative</th>
              <th className="py-2 text-right">Contribution</th>
            </tr>
          </thead>
          <tbody>
            {routeRows.map(([route, detail]) => {
              const contribution = current.data!.route_contributions[route] ?? 0
              return (
                <tr key={route} className="border-b border-slate-100">
                  <td className="py-2 font-medium">{route}</td>
                  <td className="py-2 text-right">{(detail.weight * 100).toFixed(1)}%</td>
                  <td className="py-2 text-right">{detail.base_period_fare.toLocaleString()}</td>
                  <td className="py-2 text-right">{detail.as_of_period_fare.toLocaleString()}</td>
                  <td className="py-2 text-right">{detail.relative.toFixed(3)}</td>
                  <td className={`py-2 text-right font-medium ${contribution >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                    {contribution.toFixed(3)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>

      <Card title="Calculation breakdown (transparency trace)">
        <ol className="text-sm text-slate-600 space-y-1.5 list-decimal list-inside">
          {current.data.calculation_breakdown.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ol>
      </Card>
    </div>
  )
}
