import { useState, useMemo } from 'react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend, Cell } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import type { CpiAirfareTrend, Route } from '../types'

type AnalysisTab = 'trend' | 'inflation' | 'components' | 'routes'

const TABS: { key: AnalysisTab; label: string }[] = [
  { key: 'trend', label: 'Index Trend' },
  { key: 'inflation', label: 'Inflation' },
  { key: 'components', label: 'CPI Components' },
  { key: 'routes', label: 'Route Basket' },
]

export default function Analysis() {
  const [tab, setTab] = useState<AnalysisTab>('trend')

  return (
    <div>
      <PageHeader
        title="Analysis"
        subtitle="MoSPI CPI airfare analysis · base 2024=100"
      />
      <div className="flex border-b border-slate-200 mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
              tab === t.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'trend' && <TrendTab />}
      {tab === 'inflation' && <InflationTab />}
      {tab === 'components' && <ComponentsTab />}
      {tab === 'routes' && <RoutesTab />}
    </div>
  )
}

// Tab components -----------------------------------------------------------

function TrendTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')

  if (trend.loading) return <LoadingState label="Loading CPI trend..." />
  if (trend.error) return <ErrorState message={trend.error} />

  const data = trend.data?.series ?? []
  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="No MoSPI CPI data available yet. The backend fetches it from esankhyiki.mospi.gov.in shortly after startup." />
      </Card>
    )
  }

  return (
    <Card title="Airfare CPI index over time">
      <p className="text-xs text-muted mb-3">
        Monthly values of code 07.3.3.1 (Passenger transport by air, domestic) reported by MoSPI.
      </p>
      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="period" tick={{ fontSize: 11 }} />
          <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="airfare_index" stroke="#1d4ed8" strokeWidth={2} dot={{ r: 3 }} name="Airfare CPI" />
          <Line type="monotone" dataKey="transport_index" stroke="#64748b" strokeWidth={1} dot={{ r: 2 }} name="Transport CPI" />
          <Line type="monotone" dataKey="general_index" stroke="#94a3b8" strokeWidth={1} dot={{ r: 2 }} name="General CPI" />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  )
}

function InflationTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')

  if (trend.loading) return <LoadingState label="Loading inflation data..." />
  if (trend.error) return <ErrorState message={trend.error} />

  const data = (trend.data?.series ?? []).filter((p) => p.inflation_yoy !== null)
  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="Year-over-year inflation figures will appear once MoSPI data is fetched." />
      </Card>
    )
  }

  const chart = data.map((p) => ({ period: p.period, inflation_yoy: p.inflation_yoy as number }))

  return (
    <Card title="Year-over-year airfare inflation (%)">
      <p className="text-xs text-muted mb-3">
        Airfare CPI 07.3.3.1 inflation vs the same month a year earlier.
      </p>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={chart}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="period" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} unit="%" />
          <Tooltip formatter={(v: number) => [`${v.toFixed(2)}%`, 'YoY inflation']} />
          <Bar dataKey="inflation_yoy" radius={[3, 3, 0, 0]}>
            {chart.map((d, i) => (
              <Cell key={i} fill={d.inflation_yoy >= 0 ? '#dc2626' : '#16a34a'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}

function ComponentsTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=12')

  if (trend.loading) return <LoadingState label="Loading component comparison..." />
  if (trend.error) return <ErrorState message={trend.error} />

  const data = trend.data?.series ?? []
  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="Component comparison will appear once MoSPI data is fetched." />
      </Card>
    )
  }

  return (
    <div>
      <Card className="mb-6">
        <p className="text-[11px] text-muted mb-3">
          All indices share base year 2024=100. The gap between airfare and general CPI shows
          how much faster (or slower) airfares are rising vs the headline rate.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-slate-200">
                <th className="py-2">Period</th>
                <th className="py-2 text-right">Airfare CPI</th>
                <th className="py-2 text-right">Transport CPI</th>
                <th className="py-2 text-right">General CPI</th>
                <th className="py-2 text-right">Airfare vs General</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => {
                const gap =
                  p.general_index && p.general_index > 0
                    ? ((p.airfare_index - p.general_index) / p.general_index) * 100
                    : null
                return (
                  <tr key={p.period} className="border-b border-slate-100">
                    <td className="py-2 font-medium">{p.period}</td>
                    <td className="py-2 text-right">{p.airfare_index.toFixed(2)}</td>
                    <td className="py-2 text-right text-muted">
                      {p.transport_index !== null ? p.transport_index.toFixed(2) : '\u2014'}
                    </td>
                    <td className="py-2 text-right text-muted">
                      {p.general_index !== null ? p.general_index.toFixed(2) : '\u2014'}
                    </td>
                    <td className={`py-2 text-right font-medium ${gap !== null && gap > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                      {gap !== null ? `${gap >= 0 ? '+' : ''}${gap.toFixed(2)}%` : '\u2014'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>
      <Card>
        <p className="text-xs text-muted">
          Source: MoSPI Consolidated CPI, esankhyiki.mospi.gov.in. Airfare component code 07.3.3.1.
        </p>
      </Card>
    </div>
  )
}

function RoutesTab() {
  const routesQuery = useApiQuery<Route[]>('/routes')

  if (routesQuery.loading) return <LoadingState label="Loading route basket..." />
  if (routesQuery.error) return <ErrorState message={routesQuery.error} />

  const routes = routesQuery.data ?? []
  const sorted = useMemo(() => [...routes].sort((a, b) => b.weight - a.weight), [routes])

  return (
    <div>
      <Card className="mb-6">
        <p className="text-[11px] text-muted mb-3">
          Domestic routes covered by the MoSPI CPI airfare component (07.3.3.1).
          Weight = share of all-India domestic air passenger traffic (DGCA).
        </p>
        {sorted.length === 0 ? (
          <EmptyState message="Route basket is empty." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-slate-200">
                  <th className="py-2">Route</th>
                  <th className="py-2 text-right">Weight</th>
                  <th className="py-2 text-right">Share</th>
                  <th className="py-2">Distance tier</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100">
                    <td className="py-2 font-medium">
                      {r.origin}-{r.destination}
                    </td>
                    <td className="py-2 text-right">{(r.weight * 100).toFixed(2)}%</td>
                    <td className="py-2 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="h-2 w-24 bg-slate-100 rounded overflow-hidden">
                          <div className="h-2 bg-blue-600" style={{ width: `${Math.min(100, r.weight * 500)}%` }} />
                        </div>
                        <span className="text-muted text-xs">{(r.weight * 100).toFixed(1)}%</span>
                      </div>
                    </td>
                    <td className="py-2 text-right text-muted">{r.distance_tier ?? '\u2014'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}