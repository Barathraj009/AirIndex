import { Area, AreaChart, Bar, BarChart, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend, Cell } from 'recharts'
import { Plane, TrendingUp, CalendarDays, MapPin } from 'lucide-react'
import { useRef } from 'react'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, StatCard, Card, LoadingState, ErrorState, EmptyState, TrendPill } from '../components/ui'
import { exportChartAsPNG, downloadCSV } from '../utils/exportChart'
import type { CpiAirfareIndex, CpiAirfareTrend, RouteFareSummary, LatestFare } from '../types'

const ROUTE_LABELS: Record<string, string> = {
  'DEL-BOM': 'Delhi – Mumbai',
  'DEL-HYD': 'Delhi – Hyderabad',
  'DEL-BLR': 'Delhi – Bengaluru',
  'DEL-MAA': 'Delhi – Chennai',
  'DEL-CCU': 'Delhi – Kolkata',
  'BOM-BLR': 'Mumbai – Bengaluru',
}

const BAR_COLORS = ['#1471e8', '#0ea5e9', '#6366f1', '#06b6d4', '#3b82f6', '#0284c7']

// Calendar date (YYYY-MM-DD) of "today" in India (Asia/Kolkata). The fare feed
// samples departure dates in IST, so the graph's window must start at today in
// that timezone — and drift forward as the calendar does. No hardcoded dates.
function todayInIST(): string {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  return formatter.format(new Date())
}

export default function Dashboard() {
  const routes = useApiQuery<RouteFareSummary[]>('/fares/routes')
  const latest = useApiQuery<LatestFare[]>(`/fares/latest?from_date=${todayInIST()}`)
  const current = useApiQuery<CpiAirfareIndex>('/cpi-airfare/current')
  const trend = useApiQuery<CpiAirfareTrend>('/cpi-airfare/trend?months=24')
  const chartRef = useRef<HTMLDivElement>(null)
  const chartRef2 = useRef<HTMLDivElement>(null)

  const routeRows = routes.data ?? []
  const latestRows = latest.data ?? []
  const withFares = routeRows.filter((r) => r.n_valid > 0 && r.avg_fare !== null)
  const avgFare = withFares.length
    ? withFares.reduce((s, r) => s + (r.avg_fare ?? 0), 0) / withFares.length
    : null
  const minFare = withFares.length ? Math.min(...withFares.map((r) => r.min_fare ?? Infinity)) : null
  const maxFare = withFares.length ? Math.max(...withFares.map((r) => r.max_fare ?? 0)) : null

  // Snapshot collection date (when the fares were pulled from Google Flights).
  const collectionDate = latestRows.length
    ? latestRows
        .map((f) => f.collection_timestamp?.slice(0, 10))
        .sort()
        .reverse()[0]
    : null

  // Group observations by departure date: show avg fare per date + count.
  // Only dates on/after today (timezone-safe) are shown; the backend is asked
  // for the same window via from_date, so no stale fares appear.
  const todayStr = todayInIST()
  const byDateMap = new Map<string, { date: string; fares: number[]; routes: Set<string> }>()
  for (const f of latestRows) {
    if (f.total_fare === null) continue
    const key = f.travel_date
    if (key < todayStr) continue
    if (!byDateMap.has(key)) byDateMap.set(key, { date: key, fares: [], routes: new Set() })
    const g = byDateMap.get(key)!
    g.fares.push(f.total_fare)
    g.routes.add(`${f.origin}-${f.destination}`)
  }
  const fareByDate = Array.from(byDateMap.values())
    .map((g) => ({
      date: g.date,
      avg_fare: Math.round(g.fares.reduce((a, b) => a + b, 0) / g.fares.length),
      n: g.fares.length,
      routes: ROUTE_LABELS[[...g.routes][0]] ?? [...g.routes][0],
    }))
    .sort((a, b) => a.date.localeCompare(b.date))

  const buildRoute = withFares
    .map((r) => ({
      route: r.route,
      label: ROUTE_LABELS[r.route] ?? r.route,
      avg_fare: Math.round(r.avg_fare ?? 0),
      min_fare: r.min_fare ?? 0,
      max_fare: r.max_fare ?? 0,
    }))
    .sort((a, b) => b.avg_fare - a.avg_fare)

  const momPct = useMemoMom(trend.data?.series ?? [], current.data?.period ?? null)

  if (current.loading) return <LoadingState label="Loading fare data..." />
  if (routes.error && current.error) return <ErrorState message={routes.error} onRetry={routes.refetch} />
  if (avgFare === null && !current.data?.available) {
    return (
      <>
        <PageHeader title="Airfare Tracker" subtitle="Google Flights route fares · INR" />
        <Card>
          <EmptyState message="Fare data is not available yet. Run the ingestion pipeline to collect Google Flights observations." />
        </Card>
      </>
    )
  }

  const indexVal = current.data?.airfare_index ?? null
  const baseYear = current.data?.base_year ?? 2024
  const indexPeriod = current.data?.period ?? null

  return (
    <div className="space-y-6">
      <PageHeader
        title="Airfare Tracker"
        subtitle={<>Live route fares from Google Flights · INR</>}
      />

      {/* Hero card */}
      <div className="relative overflow-hidden rounded-2xl border border-brand-500/25 bg-white shadow-card animate-fade-in-up">
        <div className="absolute inset-x-0 top-0 h-1 bg-brand-gradient" aria-hidden />
        <div className="absolute inset-0 bg-brand-gradient opacity-[0.04]" aria-hidden />
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-brand-500/10 blur-3xl" aria-hidden />
        <div className="relative flex flex-col gap-6 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-brand-600">
              <Plane size={13} />
              Current Fare Snapshot
            </div>
            <div className="mt-3 flex items-baseline gap-3">
              <span className="text-5xl font-bold tracking-tight text-brand-700 tabular-nums">
                {avgFare !== null ? `₹${avgFare.toFixed(0)}` : '—'}
              </span>
              <span className="text-sm font-medium text-muted">avg one-way fare · {withFares.length} routes</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
              {collectionDate && (
                <span className="inline-flex items-center gap-1">
                  <CalendarDays size={12} /> Collected {collectionDate}
                </span>
              )}
              {minFare !== null && (
                <span className="inline-flex items-center gap-1">
                  <TrendingUp size={12} /> Min <span className="font-semibold text-emerald-600">₹{minFare.toFixed(0)}</span>
                </span>
              )}
              {maxFare !== null && (
                <span className="inline-flex items-center gap-1">
                  <TrendingUp size={12} /> Max <span className="font-semibold text-rose-600">₹{maxFare.toFixed(0)}</span>
                </span>
              )}
            </div>
            <div className="mt-1 text-[11px] text-slate-400">
              Min/Max = cheapest and most expensive one-way fare in this snapshot.
            </div>
          </div>
        </div>
      </div>

      {/* Key stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          label="Routes Tracked"
          value={withFares.length}
          sub="Domestic sectors from Google Flights"
          icon={<MapPin size={18} />}
          accent
        />
        <StatCard
          label="Average Fare"
          value={avgFare !== null ? `₹${avgFare.toFixed(0)}` : '—'}
          sub="One-way avg across routes (INR)"
          icon={<Plane size={18} />}
        />
        <StatCard
          label="Airfare Index"
          value={indexVal !== null ? indexVal.toFixed(1) : '—'}
          sub={`Official CPI · period ${indexPeriod ?? '—'} · base ${baseYear}=100`}
          icon={<TrendingUp size={18} />}
        />
      </div>

      {/* Primary chart: fare by route (Google Flights) */}
      {buildRoute.length > 0 && (
        <Card
          title="Average Fares by Route"
          action={
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-muted">Google Flights · one-way INR</span>
              <button
                onClick={() => chartRef.current && exportChartAsPNG(chartRef.current, 'fares-by-route.png')}
                title="Download as PNG"
                className="inline-flex items-center gap-1 rounded-lg border border-line bg-white px-2 py-1 text-xs font-medium text-slate-600 hover:text-brand-700 hover:border-brand-500/40 transition-colors"
              >
                PNG
              </button>
              <button
                onClick={() =>
                  downloadCSV(
                    'fares-by-route.csv',
                    ['Route', 'Avg Fare', 'Min Fare', 'Max Fare'],
                    buildRoute.map((r) => [r.route, r.avg_fare, r.min_fare, r.max_fare])
                  )
                }
                title="Download as CSV"
                className="inline-flex items-center gap-1 rounded-lg border border-line bg-white px-2 py-1 text-xs font-medium text-slate-600 hover:text-brand-700 hover:border-brand-500/40 transition-colors"
              >
                CSV
              </button>
            </div>
          }
        >
          <p className="pb-3 text-xs text-muted">
            Average one-way fare per route collected from Google Flights. Longer bar = more expensive route.
          </p>
          <div ref={chartRef}>
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={buildRoute} margin={{ top: 8, right: 12, bottom: 40, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} angle={-15} textAnchor="end" interval={0} height={60} />
                <YAxis tickLine={false} axisLine={false} tickFormatter={(v) => `₹${v}`} domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 12 }}
                  labelStyle={{ color: '#0f172a', fontWeight: 600 }}
                  formatter={(value: number) => [`₹${value.toLocaleString()}`, 'Avg fare']}
                />
                <Legend />
                <Bar dataKey="avg_fare" name="Avg fare (INR)" radius={[6, 6, 0, 0]}>
                  {buildRoute.map((entry, i) => (
                    <Cell key={entry.route} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      {/* Secondary chart: fares by departure date (future dates are normal) */}
      {fareByDate.length > 1 && (
        <Card
          title="Fares by Departure Date"
          action={
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-muted">avg fare per departure date</span>
              <button
                onClick={() => chartRef2.current && exportChartAsPNG(chartRef2.current, 'fares-by-departure.png')}
                title="Download as PNG"
                className="inline-flex items-center gap-1 rounded-lg border border-line bg-white px-2 py-1 text-xs font-medium text-slate-600 hover:text-brand-700 hover:border-brand-500/40 transition-colors"
              >
                PNG
              </button>
              <button
                onClick={() =>
                  downloadCSV(
                    'fares-by-departure.csv',
                    ['Departure date', 'Avg Fare', '# fares', 'Route'],
                    fareByDate.map((p) => [p.date, p.avg_fare, p.n, p.routes])
                  )
                }
                title="Download as CSV"
                className="inline-flex items-center gap-1 rounded-lg border border-line bg-white px-2 py-1 text-xs font-medium text-slate-600 hover:text-brand-700 hover:border-brand-500/40 transition-colors"
              >
                CSV
              </button>
            </div>
          }
        >
          <p className="pb-3 text-xs text-muted">
            {collectionDate
              ? `Fares booked ${collectionDate} for flights departing from today onward — earlier bookings are usually cheaper.`
              : 'Each bar is the average fare for a flight departing on or after today.'}
          </p>
          <div ref={chartRef2}>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={fareByDate} margin={{ top: 8, right: 12, bottom: 40, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} angle={-15} textAnchor="end" interval={0} height={60} />
                <YAxis tickLine={false} axisLine={false} tickFormatter={(v) => `₹${v}`} domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 12 }}
                  labelStyle={{ color: '#0f172a', fontWeight: 600 }}
                  formatter={(value: number) => [`₹${value.toLocaleString()}`, 'Avg fare']}
                />
                <Legend />
                <Bar dataKey="avg_fare" name="Avg fare (INR)" radius={[6, 6, 0, 0]} fill="#0ea5e9" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      {/* Official CPI anchor */}
      {(trend.data?.series ?? []).length > 0 && (
        <Card title="Official Airfare CPI">
          <p className="pb-3 text-xs text-muted">
            Government-published MoSPI airfare CPI (code 07.3.3.1, base {baseYear}=100). This is the official
            price index — independent from the Google Flights rupee fares above.
            Shows how 'expensive' air travel is vs. the 2024 average.
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={trend.data!.series} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="gradAirfare" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0} />
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
              <Area type="monotone" dataKey="airfare_index" name="Airfare CPI" stroke="#0ea5e9" strokeWidth={2} fill="url(#gradAirfare)" dot={{ r: 2, fill: '#0ea5e9' }} activeDot={{ r: 4 }} />
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

export type { CpiAirfareIndex, CpiAirfareTrend, RouteFareSummary, LatestFare }