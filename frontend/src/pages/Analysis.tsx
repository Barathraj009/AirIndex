import { useState, useMemo, useRef } from 'react'
import {
  ComposedChart, BarChart, Bar, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Legend, Cell, Area,
} from 'recharts'
import { Download, FileSpreadsheet } from 'lucide-react'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState, TrendPill } from '../components/ui'
import { TabBar } from '../components/Tabs'
import ErrorBoundary from '../components/ErrorBoundary'
import IsometricChart from '../components/IsometricChart'
import WebGL3DChart from '../components/WebGL3DChart'
import { movingAverage, computeSeasonality, computeVolatility, fmt } from '../utils/analysis'
import { downloadCSV, exportChartAsPNG } from '../utils/exportChart'
import type { CpiAirfareTrend, Route, CpiForecastResult, CpiAirfareTrendPoint } from '../types'

type AnalysisTab = 'trend' | 'inflation' | 'components' | 'routes' | 'forecast' | 'seasonality'
type ChartMode = '2d' | '3d' | 'webgl'

function ModePicker({ mode, onChange, showWebgl = true }: { mode: ChartMode; onChange: (m: ChartMode) => void; showWebgl?: boolean }) {
  const options: { key: ChartMode; label: string }[] = [
    { key: '2d', label: '2D View' },
    { key: '3d', label: '3D View' },
    ...(showWebgl ? [{ key: 'webgl' as const, label: '3D Interactive' }] : []),
  ]
  return (
    <div role="group" aria-label="Chart view mode" className="inline-flex items-center gap-0.5 rounded-lg border border-line bg-white p-0.5 text-xs font-medium">
      {options.map((o) => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          aria-pressed={mode === o.key}
          className={`rounded-md px-3 py-1.5 transition-colors ${
            mode === o.key
              ? 'bg-brand-500/10 text-brand-700 shadow-[inset_0_0_0_1px_rgba(20,113,232,0.2)]'
              : 'text-slate-500 hover:text-slate-800'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

const TOOLTIP_STYLE = { background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 12 }

function ExportButtons({ targetName, chartRef, csvRows }: { targetName: string; chartRef: React.RefObject<HTMLDivElement | null>; csvRows?: { headers: string[]; rows: (string | number | null | undefined)[][] } }) {
  return (
    <div className="inline-flex items-center gap-1.5">
      <button
        onClick={() => chartRef.current && exportChartAsPNG(chartRef.current, `${targetName}.png`)}
        title="Download as PNG"
        className="inline-flex items-center gap-1 rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:text-brand-700 hover:border-brand-500/40 transition-colors"
      >
        <Download size={13} /> PNG
      </button>
      {csvRows && (
        <button
          onClick={() => downloadCSV(`${targetName}.csv`, csvRows.headers, csvRows.rows)}
          title="Download as CSV"
          className="inline-flex items-center gap-1 rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:text-brand-700 hover:border-brand-500/40 transition-colors"
        >
          <FileSpreadsheet size={13} /> CSV
        </button>
      )}
    </div>
  )
}

export default function Analysis() {
  const [tab, setTab] = useState<AnalysisTab>('trend')

  return (
    <div>
      <PageHeader title="Analysis" subtitle="Airfare price index analysis · base 2024=100" />
      <TabBar
        tabs={[
          { key: 'trend', label: 'Index Trend' },
          { key: 'forecast', label: 'Forecast' },
          { key: 'seasonality', label: 'Seasonality & Volatility' },
          { key: 'inflation', label: 'Inflation' },
          { key: 'components', label: 'Airfare vs Transport' },
          { key: 'routes', label: 'Route Basket' },
        ]}
        active={tab}
        onChange={(k) => setTab(k as AnalysisTab)}
      />

      <div key={tab} className="animate-fade-in-up">
        <ErrorBoundary>
          {tab === 'trend' && <TrendTab />}
          {tab === 'forecast' && <ForecastTab />}
          {tab === 'seasonality' && <SeasonalityTab />}
          {tab === 'inflation' && <InflationTab />}
          {tab === 'components' && <ComponentsTab />}
          {tab === 'routes' && <RoutesTab />}
        </ErrorBoundary>
      </div>
    </div>
  )
}

function withMovingAverage(series: CpiAirfareTrendPoint[]) {
  const momo = movingAverage(series.map((p) => p.airfare_index), 3)
  return series.map((p, i) => ({ ...p, ma3: momo[i] }))
}

function TrendTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')
  const [mode, setMode] = useState<ChartMode>('2d')
  const [showMA, setShowMA] = useState(true)
  const chartRef = useRef<HTMLDivElement>(null)

  if (trend.loading) return <LoadingState label="Loading CPI trend..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

  const data = trend.data ? withMovingAverage(trend.data.series ?? []) : []
  if (data.length === 0) {
    return (
      <Card>
        <EmptyState message="No index data available yet. The backend fetches it shortly after startup." />
      </Card>
    )
  }

  const csvRows = {
    headers: ['Period', 'Airfare CPI', 'Transport CPI', '3-month avg'],
    rows: data.map((p) => [p.period, p.airfare_index, p.transport_index, p.ma3]),
  }

  return (
    <Card
      title="Airfare CPI index over time"
      action={
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium text-slate-600">
            <input type="checkbox" checked={showMA} onChange={(e) => setShowMA(e.target.checked)} className="h-3.5 w-3.5 accent-brand-500" />
            3-mo avg
          </label>
          <ModePicker mode={mode} onChange={setMode} />
          <ExportButtons targetName="airfare-index-trend" chartRef={chartRef} csvRows={csvRows} />
        </div>
      }
    >
      <p className="pb-4 text-xs text-muted">
        Monthly values of the airfare price index (base 2024 = 100), alongside the wider transport index.
      </p>
      <div ref={chartRef}>
        {mode === '3d' ? (
          <IsometricChart
            data={data.map((p) => ({ label: p.period, value: p.airfare_index, color: '#1471e8' }))}
            height={360}
            valueFormatter={(v) => v.toFixed(2)}
          />
        ) : mode === 'webgl' ? (
          <WebGL3DChart
            data={data.map((p) => ({ label: p.period, value: p.airfare_index, color: '#1471e8' }))}
            height={360}
            valueFormatter={(v) => v.toFixed(2)}
          />
        ) : (
          <ResponsiveContainer width="100%" height={360}>
            <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="period" tickLine={false} axisLine={false} />
              <YAxis domain={['auto', 'auto']} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#0f172a', fontWeight: 600 }} />
              <Legend />
              <Bar dataKey="airfare_index" name="Airfare CPI" fill="#1471e8" radius={[4, 4, 0, 0]} maxBarSize={28} />
              {showMA && (
                <Line type="monotone" dataKey="ma3" name="3-month avg" stroke="#f59e0b" strokeWidth={2.5} strokeDasharray="5 4" dot={false} activeDot={{ r: 3.5 }} />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  )
}

function ForecastTab() {
  const forecast = useApiQuery<CpiForecastResult>('/cpi-airfare/forecast?steps=6&months=36')
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')
  const chartRef = useRef<HTMLDivElement>(null)

  if (forecast.loading || trend.loading) return <LoadingState label="Loading forecast..." />
  if (forecast.error) return <ErrorState message={forecast.error} onRetry={forecast.refetch} />

  const points = forecast.data?.forecast_points ?? []
  if (!forecast.data?.available || points.length === 0) {
    return (
      <div className="space-y-4">
        <Card>
          <EmptyState message={forecast.data?.note ?? 'Forecast requires at least 6 months of index data.'} />
        </Card>
        {trend.error && <ErrorState message={trend.error} onRetry={trend.refetch} />}
      </div>
    )
  }

  const source = trend.data?.series ?? []
  const lastObserved = source.length ? source[source.length - 1].airfare_index : null
  const historical = source.map((p) => ({
    period: p.period,
    airfare_index: p.airfare_index,
    forecast_value: null as number | null,
    lower_80: null as number | null,
    upper_80: null as number | null,
    lower_95: null as number | null,
    upper_95: null as number | null,
  }))
  if (historical.length && lastObserved !== null) {
    // Bridge: anchor the projection at the last observed value.
    const last = historical[historical.length - 1]
    last.forecast_value = lastObserved
  }
  const forecastSeries = points.map((p) => ({
    period: p.period,
    airfare_index: null as number | null,
    forecast_value: p.forecast_value as number | null,
    lower_80: p.lower_80,
    upper_80: p.upper_80,
    lower_95: p.lower_95,
    upper_95: p.upper_95,
  }))
  const combined = [...historical, ...forecastSeries]

  const last = points[points.length - 1]
  const csvRows = {
    headers: ['Period', 'Forecast', 'Lower 80%', 'Upper 80%', 'Lower 95%', 'Upper 95%'],
    rows: points.map((p) => [p.period, p.forecast_value, p.lower_80, p.upper_80, p.lower_95, p.upper_95]),
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-line bg-white p-4 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Projected next 6 months</div>
          <div className="mt-1.5 text-2xl font-bold text-ink tabular-nums">{last.period}</div>
          <div className="mt-1 text-xs text-muted">horizon end</div>
        </div>
        <div className="rounded-xl border border-line bg-white p-4 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Horizon growth</div>
          <div className="mt-1.5"><TrendPill value={forecast.data?.projected_horizon_growth_pct ?? null} /></div>
          <div className="mt-1 text-xs text-muted">projected vs latest observed</div>
        </div>
        <div className="rounded-xl border border-line bg-white p-4 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Monthly drift</div>
          <div className="mt-1.5 text-2xl font-bold text-ink tabular-nums">{fmt(forecast.data?.monthly_drift_rate, 2)}</div>
          <div className="mt-1 text-xs text-muted">index points per month</div>
        </div>
        <div className="rounded-xl border border-line bg-white p-4 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Observed months</div>
          <div className="mt-1.5 text-2xl font-bold text-ink tabular-nums">{forecast.data?.historical_periods_used ?? 0}</div>
          <div className="mt-1 text-xs text-muted">used to fit the projection</div>
        </div>
      </div>

      <Card title="Short-term airfare projection" action={<ExportButtons targetName="airfare-forecast" chartRef={chartRef} csvRows={csvRows} />}>
        <p className="pb-4 text-xs text-muted">
          Dotted segments are a statistical projection (Holt-Winters / linear trend) computed from observed data. Shaded bands are 80% and 95% confidence intervals.
        </p>
        <div ref={chartRef}>
          <ResponsiveContainer width="100%" height={360}>
            <ComposedChart data={combined} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="period" tickLine={false} axisLine={false} />
              <YAxis domain={['auto', 'auto']} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#0f172a', fontWeight: 600 }} />
              <Legend />
              <Area type="monotone" dataKey="lower_95" name="95% band" stroke="none" fill="#fb7185" fillOpacity={0.08} legendType="none" />
              <Area type="monotone" dataKey="upper_95" name="95% band" stroke="none" fill="#fb7185" fillOpacity={0} legendType="none" />
              <Area type="monotone" dataKey="lower_80" name="80% band" stroke="none" fill="#f59e0b" fillOpacity={0.12} legendType="none" />
              <Area type="monotone" dataKey="upper_80" name="80% band" stroke="none" fill="#f59e0b" fillOpacity={0} legendType="none" />
              <Bar dataKey="airfare_index" name="Observed index" fill="#1471e8" radius={[3, 3, 0, 0]} maxBarSize={22} />
              <Line type="monotone" connectNulls dataKey="forecast_value" name="Projection" stroke="#f59e0b" strokeWidth={2.5} strokeDasharray="6 5" dot={{ r: 3, fill: '#f59e0b' }} activeDot={{ r: 4 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-[11px] text-muted">Forecast shown separately, never merged with official values.</p>
      </Card>
    </div>
  )
}

function SeasonalityTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=120')
  const chartRef = useRef<HTMLDivElement>(null)

  const series = trend.data?.series ?? []
  const seasonal = useMemo(() => computeSeasonality(series), [series])
  const volatility = useMemo(() => computeVolatility(series), [series])

  if (trend.loading) return <LoadingState label="Loading seasonality data..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

  if (series.length < 3) {
    return (
      <Card>
        <EmptyState message="Seasonality analysis needs at least a few months of index data." />
      </Card>
    )
  }

  const maxAbsDev = Math.max(...seasonal.map((r) => Math.abs(r.deviationPct)), 0.01)

  const csvRows = {
    headers: ['Month', 'Average Airfare CPI', 'Deviation %', 'Years observed'],
    rows: seasonal.map((r) => [r.month, r.avgIndex || null, r.deviationPct, r.count]),
  }

  const volTone: Record<string, string> = {
    CALM: 'text-emerald-600 bg-emerald-500/10 border-emerald-500/25',
    MODERATE: 'text-amber-600 bg-amber-500/10 border-amber-500/25',
    ELEVATED: 'text-rose-600 bg-rose-500/10 border-rose-500/25',
  }

  return (
    <div className="space-y-5">
      <Card title="Month-of-year seasonality" action={<ExportButtons targetName="seasonality" chartRef={chartRef} csvRows={csvRows} />}>
        <p className="pb-4 text-xs text-muted">
          Average airfare index by calendar month, expressed as % deviation from the overall average. Warm cells = pricier months to fly.
        </p>
        <div ref={chartRef}>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6">
            {seasonal.map((r) => {
              if (r.count === 0) {
                return (
                  <div key={r.month} className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line bg-slate-50/60 p-4 text-center">
                    <div className="text-sm font-semibold text-slate-400">{r.month}</div>
                    <div className="mt-1 text-[11px] text-slate-300">no data</div>
                  </div>
                )
              }
              const intensity = Math.abs(r.deviationPct) / maxAbsDev
              const warm = r.deviationPct >= 0
              const bg = warm
                ? `rgba(244, 63, 94, ${0.12 + intensity * 0.5})`
                : `rgba(16, 185, 129, ${0.12 + intensity * 0.5})`
              return (
                <div key={r.month} className="flex flex-col items-center justify-center rounded-xl border border-line p-4 text-center" style={{ background: bg }}>
                  <div className="text-sm font-semibold text-ink">{r.month}</div>
                  <div className="mt-1 text-lg font-bold tabular-nums text-ink">{fmt(r.avgIndex)}</div>
                  <TrendPill value={r.deviationPct} />
                  <div className="mt-1 text-[10px] text-muted">{r.count} yr{r.count > 1 ? 's' : ''}</div>
                </div>
              )
            })}
          </div>
        </div>
      </Card>

      <Card title="Volatility gauge">
        <p className="pb-4 text-xs text-muted">
          Standard deviation of month-over-month airfare inflation. Lower = steadier fares.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {volatility.map((v) => (
            <div key={v.label} className="rounded-xl border border-line bg-white p-4 shadow-card">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">{v.label} std dev</div>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-3xl font-bold tabular-nums text-ink">{v.stdDev}</span>
                <span className="text-sm text-muted">pp MoM</span>
              </div>
              <div className="mt-2">
                <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold ${volTone[v.level]}`}>
                  {v.level === 'CALM' ? 'CALM' : v.level === 'MODERATE' ? 'MODERATE' : 'ELEVATED'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function InflationTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')
  const [mode, setMode] = useState<ChartMode>('2d')
  const chartRef = useRef<HTMLDivElement>(null)

  if (trend.loading) return <LoadingState label="Loading inflation data..." />
  if (trend.error) return <ErrorState message={trend.error} onRetry={trend.refetch} />

  const raw = trend.data?.series ?? []
  if (raw.length === 0) {
    return (
      <Card>
        <EmptyState message="Year-over-year inflation figures will appear once index data is available." />
      </Card>
    )
  }

  // Keep the full window so the missing months are visible as gaps,
  // with a note explaining why YoY is unavailable for the early part.
  const chart = raw.map((p) => ({
    period: p.period,
    inflation_yoy: p.inflation_yoy as number | null,
    mom_pct: null as number | null,
  }))
  for (let i = 1; i < raw.length; i++) {
    const prev = raw[i - 1].airfare_index
    if (prev > 0) {
      chart[i].mom_pct = ((raw[i].airfare_index - prev) / prev) * 100
    }
  }

  const yoyPoints = chart.filter((d): d is { period: string; inflation_yoy: number; mom_pct: number | null } => d.inflation_yoy !== null)
  const avg = yoyPoints.length ? yoyPoints.reduce((s, d) => s + d.inflation_yoy, 0) / yoyPoints.length : 0
  const latest = yoyPoints[yoyPoints.length - 1]

  const csvRows = {
    headers: ['Period', 'YoY inflation %', 'MoM %'],
    rows: chart.map((d) => [d.period, d.inflation_yoy, d.mom_pct]),
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-line bg-white p-4 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">12-mo avg YoY inflation</div>
          <div className="mt-1.5 text-2xl font-bold text-ink tabular-nums">{avg.toFixed(2)}%</div>
          <div className="mt-1 text-xs text-muted">average over the available YoY months</div>
        </div>
        <div className="rounded-xl border border-line bg-white p-4 shadow-card">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Latest month</div>
          <div className="mt-1.5"><TrendPill value={latest?.inflation_yoy ?? null} /></div>
          <div className="mt-1 text-xs text-muted">{latest?.period ?? '\u2014'}</div>
        </div>
      </div>
      <Card
        title="Year-over-year airfare inflation (%)"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <ModePicker mode={mode} onChange={setMode} />
            <ExportButtons targetName="airfare-inflation" chartRef={chartRef} csvRows={csvRows} />
          </div>
        }
      >
        <p className="pb-4 text-xs text-muted">
          Airfare inflation vs the same month a year earlier. Positive bars = fares more expensive than a year ago. The gap
          before Jan 2026 is because the base 2024=100 MoSPI series only began in Jan 2025 — a full year is needed to compute
          YoY.
        </p>
        <div ref={chartRef}>
          {mode === '3d' ? (
            <>
              <IsometricChart
                data={yoyPoints.map((d) => ({ label: d.period, value: d.inflation_yoy, color: d.inflation_yoy >= 0 ? '#f43f5e' : '#10b981' }))}
                height={320}
                valueFormatter={(v) => `${v.toFixed(2)}%`}
              />
              <p className="mt-1 text-[11px] text-muted">Green bars = fares lower than a year earlier.</p>
            </>
          ) : mode === 'webgl' ? (
            <WebGL3DChart
              data={yoyPoints.map((d) => ({ label: d.period, value: d.inflation_yoy, color: d.inflation_yoy >= 0 ? '#f43f5e' : '#10b981' }))}
              height={320}
              valueFormatter={(v) => `${v.toFixed(2)}%`}
            />
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={chart} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="period" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} unit="%" />
                <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#0f172a', fontWeight: 600 }} formatter={(v: unknown) => (v == null || v === '' ? ['\u2014', 'YoY inflation'] : [`${Number(v).toFixed(2)}%`, 'YoY inflation'])} />
                <Bar dataKey="inflation_yoy" radius={[4, 4, 0, 0]}>
                  {chart.map((d, i) => (
                    <Cell key={i} fill={d.inflation_yoy != null && d.inflation_yoy >= 0 ? '#f43f5e' : '#10b981'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>
    </div>
  )
}

function ComponentsTab() {
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=12')
  const [mode, setMode] = useState<ChartMode>('2d')
  const chartRef = useRef<HTMLDivElement>(null)

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

  const csvRows = {
    headers: ['Period', 'Airfare CPI', 'Transport CPI', 'Gap %'],
    rows: data.map((p) => {
      const gap = p.transport_index && p.transport_index > 0 ? ((p.airfare_index - p.transport_index) / p.transport_index) * 100 : null
      return [p.period, p.airfare_index, p.transport_index, gap]
    }),
  }

  return (
    <div className="space-y-5">
      <Card
        title="Airfare vs Transport"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <ModePicker mode={mode} onChange={setMode} />
            <ExportButtons targetName="airfare-vs-transport" chartRef={chartRef} csvRows={csvRows} />
          </div>
        }
      >
        <p className="pb-4 text-[11px] text-muted">
          Both indices share base year 2024=100. The gap shows how much faster airfares climb than transport prices overall.
        </p>
        <div ref={chartRef}>
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
          ) : mode === 'webgl' ? (
            <WebGL3DChart
              data={data.map((p) => ({ label: p.period, value: p.airfare_index, color: '#1471e8' }))}
              height={320}
              valueFormatter={(v) => v.toFixed(2)}
            />
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
        </div>
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

  const routes = routesQuery.data ?? []
  const sorted = useMemo(() => [...routes].sort((a, b) => b.weight - a.weight), [routes])
  const rows = useMemo(
    () => sorted.map((r) => ({ route: `${r.origin}\u2013${r.destination}`, weight: r.weight })),
    [sorted]
  )

  if (routesQuery.loading) return <LoadingState label="Loading route basket..." />
  if (routesQuery.error) return <ErrorState message={routesQuery.error} onRetry={routesQuery.refetch} />

  return (
    <div className="space-y-5">
      <Card title="Route basket weights" action={<ModePicker mode={mode} onChange={setMode} showWebgl={false} />}>
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