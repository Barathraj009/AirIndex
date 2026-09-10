import { useState, useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend, Cell } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState, TrendPill } from '../components/ui'
import { TabBar } from '../components/Tabs'
import IsometricChart from '../components/IsometricChart'
import type { CpiAirfareTrend, Route } from '../types'

type AnalysisTab = 'trend' | 'inflation' | 'components' | 'routes'
type ChartMode = '2d' | '3d'

function ModePicker({ mode, onChange }: { mode: ChartMode; onChange: (m: ChartMode) => void }) {
  return (
    <div role="group" aria-label="Chart view mode" className="inline-flex items-center gap-0.5 rounded-lg border border-line bg-white p-0.5 text-xs font-medium">
      {(['2d', '3d'] as const).map((m) => (
        <button
          key={m}
          onClick={() => onChange(m)}
          aria-pressed={mode === m}
          className={`rounded-md px-3 py-1.5 transition-colors ${
            mode === m
              ? 'bg-brand-500/10 text-brand-700 shadow-[inset_0_0_0_1px_rgba(20,113,232,0.2)]'
              : 'text-slate-500 hover:text-slate-800'
          }`}
        >
          {m === '2d' ? '2D View' : '3D View'}
        </button>
      ))}
    </div>
  )
}

const TOOLTIP_STYLE = { background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 12 }

export default function Analysis() {
  const [tab, setTab] = useState<AnalysisTab>('trend')

  return (
    <div>
      <PageHeader title="Analysis" subtitle="Airfare price index analysis · base 2024=100" />
      <TabBar
        tabs={[
          { key: 'trend', label: 'Index Trend' },
          { key: 'inflation', label: 'Inflation' },
          { key: 'components', label: 'Airfare vs Transport' },
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
  const [mode, setMode] = useState<ChartMode>('2d')

  if (trend.loading) return <LoadingState label="Loading CPI trend..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

  const data = trend.data?.series ?? []
  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="No index data available yet. The backend fetches it shortly after startup." />
      </Card>
    )
  }

  return (
    <Card title="Airfare CPI index over time" action={<ModePicker mode={mode} onChange={setMode} />}>
      <p className="pb-4 text-xs text-muted">
        Monthly values of the airfare price index (base 2024 = 100), alongside the wider transport index.
      </p>
      {mode === '3d' ? (
        <IsometricChart
          data={data.map((p) => ({ label: p.period, value: p.airfare_index, color: '#1471e8' }))}
          height={360}
          valueFormatter={(v) => v.toFixed(2)}
        />
      ) : (
        <ResponsiveContainer width="100%" height={360}>
          <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="period" tickLine={false} axisLine={false} />
            <YAxis domain={['auto', 'auto']} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#0f172a', fontWeight: 600 }} />
            <Legend />
            <Bar dataKey="airfare_index" name="Airfare CPI" fill="#1471e8" radius={[4, 4, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  )
}

function InflationTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')
  const [mode, setMode] = useState<ChartMode>('2d')

  if (trend.loading) return <LoadingState label="Loading inflation data..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

  const data = (trend.data?.series ?? []).filter((p) => p.inflation_yoy !== null)
  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="Year-over-year inflation figures will appear once index data is available." />
      </Card>
    )
  }

  const chart = data.map((p) => ({ period: p.period, inflation_yoy: p.inflation_yoy as number }))
  const avg = chart.reduce((s, d) => s + d.inflation_yoy, 0) / chart.length
  const latest = chart[chart.length - 1]

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-line bg-white p-4 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">12-mo avg YoY inflation</div>
          <div className="mt-1.5 text-2xl font-bold text-ink tabular-nums">{avg.toFixed(2)}%</div>
          <div className="mt-1 text-xs text-muted">average over the displayed window</div>
        </div>
        <div className="rounded-xl border border-line bg-white p-4 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Latest month</div>
          <div className="mt-1.5"><TrendPill value={latest.inflation_yoy} /></div>
          <div className="mt-1 text-xs text-muted">{latest.period}</div>
        </div>
      </div>
      <Card title="Year-over-year airfare inflation (%)" action={<ModePicker mode={mode} onChange={setMode} />}>
        <p className="pb-4 text-xs text-muted">
          Airfare inflation vs the same month a year earlier. Positive bars = fares more expensive than a year ago.
        </p>
        {mode === '3d' ? (
          <>
            <IsometricChart
              data={chart.map((d) => ({ label: d.period, value: d.inflation_yoy, color: d.inflation_yoy >= 0 ? '#f43f5e' : '#10b981' }))}
              height={320}
              valueFormatter={(v) => `${v.toFixed(2)}%`}
            />
            <p className="mt-1 text-[11px] text-muted">Green bars = fares lower than a year earlier.</p>
          </>
        ) : (
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
        )}
      </Card>
    </div>
  )
}

function ComponentsTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=12')
  const [mode, setMode] = useState<ChartMode>('2d')

  if (trend.loading) return <LoadingState label="Loading component comparison..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

  const data = trend.data?.series ?? []
  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="Component comparison will appear once index data is available." />
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      <Card title="Airfare vs Transport" action={<ModePicker mode={mode} onChange={setMode} />}>
        <p className="pb-4 text-[11px] text-muted">
          Both indices share base year 2024=100. The gap shows how much faster airfares climb than transport prices overall.
        </p>
        {mode === '3d' ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <p className="pb-2 text-center text-xs font-semibold text-brand-700">Airfare CPI</p>
              <IsometricChart
                data={data.map((p) => ({ label: p.period, value: p.airfare_index, color: '#1471e8' }))}
                height={280}
                valueFormatter={(v) => v.toFixed(2)}
              />
            </div>
            <div>
              <p className="pb-2 text-center text-xs font-semibold text-sky-600">Transport CPI</p>
              <IsometricChart
                data={data.map((p) => ({ label: p.period, value: p.transport_index ?? p.airfare_index, color: '#0ea5e9' }))}
                height={280}
                valueFormatter={(v) => v.toFixed(2)}
              />
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="period" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#0f172a', fontWeight: 600 }} />
              <Legend />
              <Bar dataKey="airfare_index" name="Airfare CPI" fill="#1471e8" radius={[4, 4, 0, 0]} maxBarSize={22} />
              <Bar dataKey="transport_index" name="Transport CPI" fill="#0ea5e9" radius={[4, 4, 0, 0]} maxBarSize={22} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>
      <Card>
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-line bg-slate-50">
                <th className="py-2.5 px-3 font-medium">Period</th>
                <th className="py-2.5 px-3 text-right font-medium">Airfare CPI</th>
                <th className="py-2.5 px-3 text-right font-medium">Transport CPI</th>
                <th className="py-2.5 px-3 text-right font-medium">Transport vs Airfare</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => {
                const gap = p.transport_index && p.transport_index > 0 ? ((p.airfare_index - p.transport_index) / p.transport_index) * 100 : null
                return (
                  <tr key={p.period} className="border-b border-lineSoft hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 px-3 font-medium text-ink">{p.period}</td>
                    <td className="py-2.5 px-3 text-right tabular-nums">{p.airfare_index.toFixed(2)}</td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-muted">
                      {p.transport_index !== null ? p.transport_index.toFixed(2) : '\u2014'}
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
    </div>
  )
}

function RoutesTab() {
  const routesQuery = useApiQuery<Route[]>('/routes')
  const [mode, setMode] = useState<ChartMode>('2d')

  if (routesQuery.loading) return <LoadingState label="Loading route basket..." />
  if (routesQuery.error) return <ErrorState message={routesQuery.error} onRetry={routesQuery.refetch} />

  const routes = routesQuery.data ?? []
  const sorted = useMemo(() => [...routes].sort((a, b) => b.weight - a.weight), [routes])
  const rows = useMemo(
    () => sorted.map((r) => ({ route: `${r.origin}\u2013${r.destination}`, weight: r.weight })),
    [sorted]
  )

  return (
    <div className="space-y-5">
      <Card title="Route basket weights" action={<ModePicker mode={mode} onChange={setMode} />}>
        <p className="pb-4 text-[11px] text-muted">
          Domestic route basket behind the airfare index, weighted by share of all-India domestic air passenger traffic.
        </p>
        {sorted.length === 0 ? (
          <EmptyState message="Route basket is empty." />
        ) : mode === '3d' ? (
          <IsometricChart
            data={sorted.map((r) => ({ label: `${r.origin}\u2013${r.destination}`, value: r.weight * 100, color: '#1471e8' }))}
            height={300}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(240, sorted.length * 30 + 40)}>
            <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="route" width={88} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#0f172a', fontWeight: 600 }} formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, 'Weight']} />
              <Bar dataKey="weight" fill="#1471e8" radius={[0, 4, 4, 0]} barSize={14} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>
      <Card>
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
                      {`${r.origin}\u2013${r.destination}`}
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
      </Card>
    </div>
  )
}