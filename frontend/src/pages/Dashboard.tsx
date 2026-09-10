import { Area, AreaChart, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend } from 'recharts'
import { Plane, TrendingUp, CalendarDays } from 'lucide-react'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, StatCard, Card, LoadingState, ErrorState, EmptyState, TrendPill } from '../components/ui'
import type { CpiAirfareIndex, CpiAirfareTrend } from '../types'

export default function Dashboard() {
  const current = useApiQuery<CpiAirfareIndex>('/cpi-airfare/current')
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')

  if (current.loading) return <LoadingState label="Loading CPI data..." />
  if (current.error) return <ErrorState message={current.error} onRetry={current.refetch} />
  if (!current.data) {
    return (
      <>
        <PageHeader title="Airfare Price Index" subtitle="Airfare price index · base 2024=100" />
        <Card>
          <EmptyState message="Index data is not available yet." />
        </Card>
      </>
    )
  }

  const data = current.data
  const trendData = trend.data?.series ?? []

  if (!data.available) {
    return (
      <div>
        <PageHeader title="Airfare Price Index" subtitle="Airfare price index · base 2024=100" />
        <Card>
          <EmptyState message="Awaiting airfare index data. The backend fetches it from the price-index pipeline shortly after startup." />
        </Card>
      </div>
    )
  }

  // MoM change from trend series (fallback to null if only 1 point)
  const momPct = useMemoMom(trendData, data.period)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Airfare Price Index"
        subtitle={<>Air transport price index · Base {data.base_year}</>}
      />

      {/* Hero index card */}
      <div className="relative overflow-hidden rounded-2xl border border-brand-500/25 bg-white shadow-card animate-fade-in-up">
        <div className="absolute inset-x-0 top-0 h-1 bg-brand-gradient" aria-hidden />
        <div className="absolute inset-0 bg-brand-gradient opacity-[0.04]" aria-hidden />
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-brand-500/10 blur-3xl" aria-hidden />
        <div className="relative flex flex-col gap-6 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-brand-600">
              <Plane size={13} />
              Current Airfare Price Index
            </div>
            <div className="mt-3 flex items-baseline gap-3">
              <span className="text-5xl font-bold tracking-tight text-brand-700 tabular-nums">
                {data.airfare_index!.toFixed(2)}
              </span>
              <span className="text-sm font-medium text-muted">base 2024 = 100</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
              <span className="inline-flex items-center gap-1">
                <CalendarDays size={12} /> Period {data.period}
              </span>
              <span className="inline-flex items-center gap-1">
                <TrendingUp size={12} /> YoY <TrendPill value={data.inflation_yoy} />
              </span>
              {momPct !== null && (
                <span className="inline-flex items-center gap-1">
                  MoM <TrendPill value={momPct} />
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Key stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          label="Airfare CPI"
          value={data.airfare_index!.toFixed(2)}
          sub="Domestic air travel · base 2024=100"
          icon={<Plane size={18} />}
          accent
        />
        <StatCard
          label="Transport CPI"
          value={data.transport_index?.toFixed(2) ?? 'N/A'}
          sub="All modes of transport"
          icon={<TrendingUp size={18} />}
        />
      </div>

      {/* Trend chart */}
      {trendData.length > 0 && (
        <Card title="Index Trend" action={<span className="text-[11px] text-muted">last {trendData.length} months</span>}>
          <p className="pb-3 text-xs text-muted">
            Monthly airfare index contrasted with the wider transport index.
          </p>
          <ResponsiveContainer width="100%" height={340}>
            <AreaChart data={trendData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="gradAirfare" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#1471e8" stopOpacity={0.18} />
                  <stop offset="100%" stopColor="#1471e8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="period" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 12 }}
                labelStyle={{ color: '#0f172a', fontWeight: 600 }}
              />
              <Legend />
              <Area type="monotone" dataKey="airfare_index" name="Airfare CPI" stroke="#1471e8" strokeWidth={2.5} fill="url(#gradAirfare)" dot={{ r: 2.5, fill: '#1471e8' }} activeDot={{ r: 4 }} />
              <Area type="monotone" dataKey="transport_index" name="Transport CPI" stroke="#0ea5e9" strokeOpacity={0.6} strokeWidth={1.5} fill="none" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  )
}

function useMemoMom(trendData: CpiAirfareTrend['series'], currentPeriod: string | null): number | null {
  if (!currentPeriod || trendData.length < 2) return null
  const idx = trendData.findIndex((p) => p.period === currentPeriod)
  if (idx <= 0) return null
  const prev = trendData[idx - 1].airfare_index
  const curr = trendData[idx].airfare_index
  if (!prev) return null
  return ((curr - prev) / prev) * 100
}

export type { CpiAirfareIndex, CpiAirfareTrend }