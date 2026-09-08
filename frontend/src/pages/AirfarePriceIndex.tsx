import { useState, useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ResponsiveContainer } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, StatCard, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import type { IndexResult, IndexTrend, IndexForecastResult } from '../types'

export default function AirfarePriceIndex() {
  const periodsQuery = useApiQuery<{ periods: string[] }>('/index/available-periods')
  const periods = periodsQuery.data?.periods ?? []
  const periodsParam = periods.join(',')

  const current = useApiQuery<IndexResult>('/index/current')
  const trend = useApiQuery<IndexTrend>(periodsParam ? `/index/trend?periods=${periodsParam}` : null, [periodsParam])
  const forecastQuery = useApiQuery<IndexForecastResult>('/index/forecast?steps=3')

  const [showForecast, setShowForecast] = useState<boolean>(true)
  const [sortBy, setSortBy] = useState<'contribution' | 'route'>('contribution')

  const chartData = useMemo(() => {
    const historical = (trend.data?.series ?? []).map((p) => ({
      period: p.period,
      actual_index: p.index_value,
      forecast_index: null as number | null,
      upper_95: null as number | null,
      lower_95: null as number | null,
    }))

    if (!showForecast || !forecastQuery.data?.forecast_points) {
      return historical
    }

    // Connect the last historical point with the forecast
    if (historical.length > 0) {
      const lastHist = historical[historical.length - 1]
      lastHist.forecast_index = lastHist.actual_index
    }

    const projected = forecastQuery.data.forecast_points.map((fp) => ({
      period: fp.period,
      actual_index: null,
      forecast_index: fp.forecast_value,
      upper_95: fp.upper_95,
      lower_95: fp.lower_95,
    }))

    return [...historical, ...projected]
  }, [trend.data, forecastQuery.data, showForecast])

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

      {/* Historical Trend & Forecast Chart */}
      <Card title="Index Trajectory & Forward Forecast" className="mb-6">
        <div className="flex justify-between items-center mb-4 text-xs">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowForecast(!showForecast)}
              className={`px-3 py-1.5 rounded font-medium transition ${
                showForecast ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {showForecast ? '✓ Forward Forecast Active (+3 Months)' : '+ Show Forward Forecast'}
            </button>
            {forecastQuery.data?.forecast_available && showForecast && (
              <span className="text-muted">
                Projected 3-Mo Drift: <strong className="text-blue-700">{forecastQuery.data.projected_horizon_growth_pct > 0 ? '+' : ''}{forecastQuery.data.projected_horizon_growth_pct}%</strong>
              </span>
            )}
          </div>
        </div>

        {trend.loading && <LoadingState />}
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="period" tick={{ fontSize: 12 }} />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="actual_index" name="Observed APIx" stroke="#1d4ed8" strokeWidth={2.5} dot={{ r: 4 }} connectNulls />
              {showForecast && (
                <>
                  <Line type="monotone" dataKey="forecast_index" name="Forecast Point" stroke="#f59e0b" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 4 }} connectNulls />
                  <Line type="monotone" dataKey="upper_95" name="Upper 95% Bound" stroke="#fbbf24" strokeWidth={1} strokeDasharray="2 2" dot={false} connectNulls />
                  <Line type="monotone" dataKey="lower_95" name="Lower 95% Bound" stroke="#fbbf24" strokeWidth={1} strokeDasharray="2 2" dot={false} connectNulls />
                </>
              )}
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
