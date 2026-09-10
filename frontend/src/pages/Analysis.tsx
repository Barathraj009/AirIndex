import { useState, useMemo } from 'react'
import { AreaChart, Area, LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend, Cell } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState, TrendPill } from '../components/ui'
import { TabBar } from '../components/Tabs'
import type { CpiAirfareTrend, Route } from '../types'

type AnalysisTab = 'trend' | 'inflation' | 'components' | 'routes'

const TABS: AnalysisTab[] = ['trend', 'inflation', 'components', 'routes']

const TOOLTIP_STYLE = { background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 12 }

export default function Analysis() {
  const [tab, setTab] = useState<AnalysisTab>('trend')

  return (
    <div>
      <PageHeader
        title="Analysis"
        subtitle="MoSPI CPI airfare analysis · base 2024=100"
      />
      <TabBar
        tabs={[
          { key: 'trend', label: 'Index Trend' },
          { key: 'inflation', label: 'Inflation' },
          { key: 'components', label: 'CPI Components' },
          { key: 'routes', label: 'Route Basket' },
        ]}
        active={tab}
        onChange={(k) => setTab(k as AnalysisTab)}
      />

      <div key={tab} className="animate-fade-in-up">
        {tab === 'trend' && <TrendTab />}
        {tab === 'inflation' && <InflationTab />}
        {tab === 'components' && <ComponentsTab />}
        {tab === 'routes' && <RoutesTab />}
      </div>
    </div>
  )
}

function TrendTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')

  if (trend.loading) return <LoadingState label="Loading CPI trend..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

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
      <p className="pb-4 text-xs text-muted">
        Monthly values of code 07.3.3.1 (Passenger transport by air, domestic) reported by MoSPI.
      </p>
      <ResponsiveContainer width="100%" height={360}>
        <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="gradA" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1471e8" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#1471e8" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="period" tickLine={false} axisLine={false} />
          <YAxis domain={['auto', 'auto']} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#0f172a', fontWeight: 600 }} />
          <Legend />
          <Area type="monotone" dataKey="airfare_index" name="Airfare CPI" stroke="#1471e8" strokeWidth={2.5} fill="url(#gradA)" dot={{ r: 2.5, fill: '#1471e8' }} activeDot={{ r: 4 }} />
          <Line type="monotone" dataKey="transport_index" name="Transport CPI" stroke="#0ea5e9" strokeOpacity={0.55} strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="general_index" name="General CPI" stroke="#94a3b8" strokeWidth={1.5} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  )
}

function InflationTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')

  if (trend.loading) return <LoadingState label="Loading inflation data..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

  const data = (trend.data?.series ?? []).filter((p) => p.inflation_yoy !== null)
  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="Year-over-year inflation figures will appear once MoSPI data is fetched." />
      </Card>
    )
  }

  const chart = data.map((p) => ({ period: p.period, inflation_yoy: p.inflation_yoy as number }))
  const avg = chart.reduce((s, d) => s + d.inflation_yoy, 0) / chart.length
  const latest = chart[chart.length - 1]

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Latest YoY (12-mo avg shown)</div>
          <div className="mt-1.5 text-2xl font-bold text-ink tabular-nums">{avg.toFixed(2)}%</div>
          <div className="mt-1 text-xs text-muted">average over the displayed window</div>
        </div>
        <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Latest month</div>
          <div className="mt-1.5"><TrendPill value={latest.inflation_yoy} /></div>
          <div className="mt-1 text-xs text-muted">{latest.period}</div>
        </div>
      </div>
      <Card title="Year-over-year airfare inflation (%)">
        <p className="pb-4 text-xs text-muted">
          Airfare CPI 07.3.3.1 inflation vs the same month a year earlier. Positive bars = fares more expensive than a year ago.
        </p>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chart} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="period" tickLine={false} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} unit="%" />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#0f172a', fontWeight: 600 }} formatter={(v: number) => [`${v.toFixed(2)}%`, 'YoY inflation']} />
            <Bar dataKey="inflation_yoy" radius={[4, 4, 0, 0]}>
              {chart.map((d, i) => (
                <Cell key={i} fill={d.inflation_yoy >= 0 ? '#f43f5e' : '#10b981'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  )
}

function ComponentsTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=12')

  if (trend.loading) return <LoadingState label="Loading component comparison..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

  const data = trend.data?.series ?? []
  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="Component comparison will appear once MoSPI data is fetched." />
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      <Card>
        <p className="pb-4 text-[11px] text-muted">
          All indices share base year 2024=100. The gap between airfare and general CPI shows
          how much faster (or slower) airfares are rising vs the headline rate.
        </p>
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-line bg-slate-50">
                <th className="py-2.5 px-3 font-medium">Period</th>
                <th className="py-2.5 px-3 text-right font-medium">Airfare CPI</th>
                <th className="py-2.5 px-3 text-right font-medium">Transport CPI</th>
                <th className="py-2.5 px-3 text-right font-medium">General CPI</th>
                <th className="py-2.5 px-3 text-right font-medium">Airfare vs General</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => {
                const gap = p.general_index && p.general_index > 0 ? ((p.airfare_index - p.general_index) / p.general_index) * 100 : null
                return (
                  <tr key={p.period} className="border-b border-lineSoft hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 px-3 font-medium text-ink">{p.period}</td>
                    <td className="py-2.5 px-3 text-right tabular-nums">{p.airfare_index.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-muted">
                      {p.transport_index !== null ? p.transport_index.toFixed(2) : '\u2014'}
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-muted">
                      {p.general_index !== null ? p.general_index.toFixed(2) : '\u2014'}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      {gap !== null ? <TrendPill value={gap} /> : '\u2014'}
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
  if (routesQuery.error) return <ErrorState message={routesQuery.error} onRetry={routesQuery.refetch} />

  const routes = routesQuery.data ?? []
  const sorted = useMemo(() => [...routes].sort((a, b) => b.weight - a.weight), [routes])

  return (
    <Card>
      <p className="pb-4 text-[11px] text-muted">
        Domestic route basket behind the airfare index, weighted by share of all-India domestic air passenger traffic (DGCA).
      </p>
      {sorted.length === 0 ? (
        <EmptyState message="Route basket is empty." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-line bg-slate-50">
                <th className="py-2.5 px-3 font-medium">Route</th>
                <th className="py-2.5 px-3 font-medium">Distance tier</th>
                <th className="py-2.5 px-3 text-right font-medium">Weight</th>
                <th className="w-1/3 py-2.5 px-3 text-right font-medium">Share</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.id} className="border-b border-lineSoft hover:bg-slate-50 transition-colors">
                  <td className="py-2.5 px-3 font-medium text-ink">
                    <span className="rounded-md bg-brand-500/10 px-2 py-0.5 font-mono text-xs text-brand-700">
                      {r.origin}–{r.destination}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-muted">{r.distance_tier ?? '\u2014'}</td>
                  <td className="py-2.5 px-3 text-right tabular-nums">{(r.weight * 100).toFixed(2)}%</td>
                  <td className="py-2.5 px-3">
                    <div className="flex items-center justify-end gap-2.5">
                      <div className="h-1.5 w-28 rounded-full bg-lineSoft overflow-hidden">
                        <div className="h-full rounded-full bg-brand-gradient" style={{ width: `${Math.min(100, r.weight * 500)}%` }} />
                      </div>
                      <span className="text-xs text-muted tabular-nums">{(r.weight * 100).toFixed(1)}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}