import { LineChart, Line, Area, AreaChart, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend } from 'recharts'
import { Plane, TrendingUp, Scale, CalendarDays } from 'lucide-react'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, StatCard, Card, LoadingState, ErrorState, SourceBadge, EmptyState, InfoRow, TrendPill } from '../components/ui'
import type { CpiAirfareIndex, CpiAirfareTrend } from '../types'

export default function Dashboard() {
  const current = useApiQuery<CpiAirfareIndex>('/cpi-airfare/current')
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')

  if (current.loading) return <LoadingState label="Loading CPI data..." />
  if (current.error) return <ErrorState message={current.error} onRetry={current.refetch} />
  if (!current.data) {
    return (
      <>
        <PageHeader
          title="Airfare Price Index"
          subtitle="MoSPI CPI 07.3.3.1 · Base 2024=100"
          action={<SourceBadge sourceType="PUBLIC_DATASET" />}
        />
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
        <PageHeader
          title="Airfare Price Index"
          subtitle="MoSPI CPI 07.3.3.1 · Base 2024=100"
          action={<SourceBadge sourceType="PUBLIC_DATASET" />}
        />
        <Card>
          <EmptyState message="Awaiting MoSPI CPI airfare data. The backend fetches it from esankhyiki.mospi.gov.in shortly after startup." />
        </Card>
      </div>
    )
  }

  // MoM change from trend series (fallback to null if only 1 point)
  const momPct = useMemoMom(trendData, data.period)
  const gapVsGeneral =
    data.general_index && data.general_index > 0
      ? ((data.airfare_index! - data.general_index) / data.general_index) * 100
      : null

  return (
    <div className="space-y-6">
      <PageHeader
        title="Airfare Price Index"
        subtitle={
          <>
            Official air transport CPI sub-index · MoSPI code 07.3.3.1 · Base {data.base_year}
          </>
        }
        action={<SourceBadge sourceType="PUBLIC_DATASET" />}
      />

      {/* Hero index card */}
      <div className="relative overflow-hidden rounded-2xl border border-brand-700/30 bg-raised shadow-glow animate-fade-in-up">
        <div className="absolute inset-0 bg-brand-gradient opacity-[0.07]" aria-hidden />
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-brand-500/20 blur-3xl" aria-hidden />
        <div className="relative flex flex-col gap-6 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-brand-300">
              <Plane size={13} />
              Current Airfare Price Index
            </div>
            <div className="mt-3 flex items-baseline gap-3">
              <span className="text-5xl font-bold tracking-tight text-white tabular-nums">
                {data.airfare_index!.toFixed(2)}
              </span>
              <span className="text-sm font-medium text-muted">base 2024 = 100</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
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

          <div className="shrink-0 rounded-xl border border-line bg-base/50 px-5 py-4 sm:text-right">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">vs General CPI</div>
            <div className={`mt-1.5 text-2xl font-bold tabular-nums ${gapVsGeneral !== null && gapVsGeneral > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
              {gapVsGeneral !== null ? `${gapVsGeneral >= 0 ? '+' : ''}${gapVsGeneral.toFixed(2)}%` : '—'}
            </div>
            <div className="mt-1 text-[11px] text-muted">
              {gapVsGeneral !== null && gapVsGeneral > 0
                ? 'Airfares rising faster than headline CPI'
                : 'Airfares tracking near headline CPI'}
            </div>
          </div>
        </div>
      </div>

      {/* Key stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          label="Airfare CPI"
          value={data.airfare_index!.toFixed(2)}
          sub={`Code ${data.cpi_code || '07.3.3.1'} · MoSPI`}
          icon={<Plane size={18} />}
          accent
        />
        <StatCard
          label="Transport CPI"
          value={data.transport_index?.toFixed(2) ?? 'N/A'}
          sub="Division 07 · all transport"
          icon={<TrendingUp size={18} />}
        />
        <StatCard
          label="General CPI"
          value={data.general_index?.toFixed(2) ?? 'N/A'}
          sub="All-India headline index"
          icon={<Scale size={18} />}
        />
      </div>

      {/* Trend chart */}
      {trendData.length > 0 && (
        <Card
          title="Index Trend"
          action={<span className="text-[11px] text-muted">last {trendData.length} months</span>}
        >
          <p className="pb-3 text-xs text-muted">
            Monthly airfare CPI contrasted with the transport and all-item indices.
          </p>
          <ResponsiveContainer width="100%" height={340}>
            <AreaChart data={trendData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="gradAirfare" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#54b1ff" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#54b1ff" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradGeneral" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#64748b" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#64748b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="period" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ background: '#131c2e', border: '1px solid #1e293b', borderRadius: 12 }}
                labelStyle={{ color: '#e2e8f0', fontWeight: 600 }}
              />
              <Legend />
              <Area type="monotone" dataKey="airfare_index" name="Airfare CPI" stroke="#54b1ff" strokeWidth={2.5} fill="url(#gradAirfare)" dot={{ r: 2.5, fill: '#54b1ff' }} activeDot={{ r: 4 }} />
              <Area type="monotone" dataKey="transport_index" name="Transport CPI" stroke="#38bdf8" strokeOpacity={0.6} strokeWidth={1.5} fill="none" dot={false} />
              <Area type="monotone" dataKey="general_index" name="General CPI" stroke="#64748b" strokeWidth={1.5} fill="url(#gradGeneral)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Data source info */}
      <Card title="Data Source">
        <div className="divide-y divide-lineSoft">
          <InfoRow label="Source">Ministry of Statistics and Programme Implementation (MoSPI)</InfoRow>
          <InfoRow label="Portal">
            <a href="https://esankhyiki.mospi.gov.in" target="_blank" rel="noopener noreferrer" className="text-brand-400 hover:underline">
              esankhyiki.mospi.gov.in
            </a>
          </InfoRow>
          <InfoRow label="CPI Code">07.3.3.1 - Passenger transport by air, domestic</InfoRow>
          <InfoRow label="Base Year">{data.base_year}</InfoRow>
          <InfoRow label="Last Fetched">
            {data.fetched_at ? new Date(data.fetched_at).toLocaleString() : 'N/A'}
          </InfoRow>
        </div>
      </Card>
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

// Recharts LineChart import retained for potential future toggle views
export type { CpiAirfareIndex, CpiAirfareTrend }