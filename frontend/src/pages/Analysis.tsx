import { useState, useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Cell } from 'recharts'
import { LineChart, Line } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import type { IndexResult, Route } from '../types'

type AnalysisTab = 'routes' | 'airlines' | 'lead-time' | 'heatmap'

const TABS: { key: AnalysisTab; label: string }[] = [
  { key: 'routes', label: 'Routes' },
  { key: 'airlines', label: 'Airlines' },
  { key: 'lead-time', label: 'Lead Time' },
  { key: 'heatmap', label: 'Heatmap' },
]

export default function Analysis() {
  const [tab, setTab] = useState<AnalysisTab>('routes')

  return (
    <div>
      <PageHeader title="Analysis" subtitle="Fare trends, contributions, and pricing dynamics" />
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
      {tab === 'routes' && <RoutesTab />}
      {tab === 'airlines' && <AirlinesTab />}
      {tab === 'lead-time' && <LeadTimeTab />}
      {tab === 'heatmap' && <HeatmapTab />}
    </div>
  )
}

function RoutesTab() {
  const indexQuery = useApiQuery<IndexResult>('/index/current')
  const [selected, setSelected] = useState<string | null>(null)

  const routeFares = indexQuery.data?.route_fares ?? {}
  const chartData = useMemo(
    () =>
      Object.entries(routeFares)
        .map(([route, d]) => ({
          route,
          change_pct: (d.relative - 1) * 100,
        }))
        .sort((a, b) => b.change_pct - a.change_pct),
    [routeFares],
  )

  if (indexQuery.loading) return <LoadingState label="Loading route analysis..." />
  if (indexQuery.error) return <ErrorState message={indexQuery.error} />
  if (!indexQuery.data) return null

  const detail = selected ? indexQuery.data.route_fares[selected] : null

  return (
    <div>
      <Card title="Fare change by route (%)" className="mb-6">
        <ResponsiveContainer width="100%" height={Math.max(280, chartData.length * 26)}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 24 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis type="number" tick={{ fontSize: 12 }} unit="%" />
            <YAxis dataKey="route" type="category" width={70} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
            <Bar
              dataKey="change_pct"
              onClick={(d: any) => setSelected(d.route)}
              cursor="pointer"
              radius={[0, 3, 3, 0]}
            >
              {chartData.map((d) => (
                <Cell key={d.route} fill={d.change_pct >= 0 ? '#dc2626' : '#16a34a'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <p className="text-xs text-muted mt-2">Click a bar to see route detail below.</p>
      </Card>

      {detail && selected && (
        <Card title={`Route detail \u2014 ${selected}`}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-xs text-muted uppercase">Weight</div>
              <div className="font-semibold">{(detail.weight * 100).toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-xs text-muted uppercase">Base fare</div>
              <div className="font-semibold">{`\u20b9${detail.base_period_fare.toLocaleString()}`}</div>
            </div>
            <div>
              <div className="text-xs text-muted uppercase">Current fare</div>
              <div className="font-semibold">{`\u20b9${detail.as_of_period_fare.toLocaleString()}`}</div>
            </div>
            <div>
              <div className="text-xs text-muted uppercase">Price relative</div>
              <div className="font-semibold">{detail.relative.toFixed(3)}</div>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

function AirlinesTab() {
  interface AirlineRow {
    airline: string
    valid_observations: number
    median_fare: number
    observation_share_pct: number
  }

  const airlinesQuery = useApiQuery<{ airlines: AirlineRow[] }>('/analytics/airlines')
  const indexQuery = useApiQuery<IndexResult>('/index/current')

  if (airlinesQuery.loading) return <LoadingState label="Loading airline analysis..." />
  if (airlinesQuery.error) return <ErrorState message={airlinesQuery.error} />

  const airlines = airlinesQuery.data?.airlines ?? []
  const contributions = indexQuery.data?.airline_contributions ?? {}

  if (airlines.length === 0) return <EmptyState message="No airline data available yet." />

  return (
    <div>
      <Card title="Median fare by airline" className="mb-6">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={airlines}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="airline" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v: number) => `\u20b9${v.toLocaleString()}`} />
            <Bar dataKey="median_fare" fill="#1d4ed8" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Airline comparison">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted border-b border-slate-200">
              <th className="py-2">Airline</th>
              <th className="py-2 text-right">Observations</th>
              <th className="py-2 text-right">Share</th>
              <th className="py-2 text-right">Median fare</th>
              <th className="py-2 text-right">Index contrib.</th>
            </tr>
          </thead>
          <tbody>
            {airlines.map((a) => {
              const contrib = contributions[a.airline]
              return (
                <tr key={a.airline} className="border-b border-slate-100">
                  <td className="py-2 font-medium">{a.airline}</td>
                  <td className="py-2 text-right">{a.valid_observations.toLocaleString()}</td>
                  <td className="py-2 text-right">{a.observation_share_pct.toFixed(1)}%</td>
                  <td className="py-2 text-right">{`\u20b9${a.median_fare.toLocaleString()}`}</td>
                  <td className={`py-2 text-right font-medium ${contrib !== undefined ? (contrib >= 0 ? 'text-red-600' : 'text-emerald-600') : 'text-muted'}`}>
                    {contrib !== undefined ? contrib.toFixed(3) : '\u2014'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="text-xs text-muted mt-3">
          Index contribution is a transparency proxy weighted by each airline's observed share of valid
          fare quotes in the current period.
        </p>
      </Card>
    </div>
  )
}

function LeadTimeTab() {
  interface LeadTimePoint {
    booking_window_days: number
    median_fare: number
  }
  interface LeadTimeResponse {
    origin: string
    destination: string
    points: LeadTimePoint[]
    pct_increase_last_minute_vs_cheapest: number | null
  }
  interface RouteRanking {
    routes: Array<{ route: string; t1_vs_t45_pct_increase: number }>
  }

  const routesQuery = useApiQuery<Route[]>('/routes')
  const rankingQuery = useApiQuery<RouteRanking>('/analytics/lead-time/all-routes-summary')

  const routes = routesQuery.data ?? []
  const [selectedRoute, setSelectedRoute] = useState('')

  const activeRoute = selectedRoute || (routes[0] ? `${routes[0].origin}-${routes[0].destination}` : '')
  const [origin, destination] = activeRoute ? activeRoute.split('-') : ['', '']

  const leadTimeQuery = useApiQuery<LeadTimeResponse>(
    origin && destination ? `/analytics/lead-time?origin=${origin}&destination=${destination}` : null,
    [origin, destination],
  )

  return (
    <div>
      <Card title="Fare vs booking window" className="mb-6">
        <div className="mb-4">
          <select
            value={activeRoute}
            onChange={(e) => setSelectedRoute(e.target.value)}
            className="text-sm border border-slate-300 rounded px-2 py-1.5"
          >
            {routes.map((r) => (
              <option key={r.id} value={`${r.origin}-${r.destination}`}>
                {r.origin}-{r.destination}
              </option>
            ))}
          </select>
        </div>

        {leadTimeQuery.loading && <LoadingState />}
        {leadTimeQuery.error && <ErrorState message={leadTimeQuery.error} />}
        {leadTimeQuery.data && leadTimeQuery.data.points.length > 0 ? (
          <>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={[...leadTimeQuery.data.points].sort((a, b) => b.booking_window_days - a.booking_window_days)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="booking_window_days" tickFormatter={(v) => `T+${v}`} tick={{ fontSize: 12 }} reversed />
                <YAxis tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
                <Tooltip labelFormatter={(v) => `T+${v}`} formatter={(v: number) => [`\u20b9${v.toLocaleString()}`, 'Median fare']} />
                <Line type="monotone" dataKey="median_fare" stroke="#1d4ed8" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
            {leadTimeQuery.data.pct_increase_last_minute_vs_cheapest !== null && (
              <p className="text-sm text-muted mt-2">
                Booking at T+1 costs{' '}
                <span className="font-semibold text-red-600">
                  {leadTimeQuery.data.pct_increase_last_minute_vs_cheapest.toFixed(1)}%
                </span>{' '}
                more than the cheapest window on this route.
              </p>
            )}
          </>
        ) : (
          !leadTimeQuery.loading && <EmptyState message="No valid data for this route yet." />
        )}
      </Card>

      <Card title="Routes with the sharpest last-minute markup (T+1 vs T+45)">
        {rankingQuery.loading && <LoadingState />}
        {rankingQuery.data && rankingQuery.data.routes.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-slate-200">
                <th className="py-2">Route</th>
                <th className="py-2 text-right">T+1 vs T+45 markup</th>
              </tr>
            </thead>
            <tbody>
              {rankingQuery.data.routes.slice(0, 10).map((r) => (
                <tr key={r.route} className="border-b border-slate-100">
                  <td className="py-2 font-medium">{r.route}</td>
                  <td className="py-2 text-right text-red-600 font-medium">+{r.t1_vs_t45_pct_increase.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          !rankingQuery.loading && <EmptyState message="Not enough data yet to rank routes." />
        )}
      </Card>
    </div>
  )
}

function HeatmapTab() {
  const indexQuery = useApiQuery<IndexResult>('/index/current')

  if (indexQuery.loading) return <LoadingState label="Building heatmap..." />
  if (indexQuery.error) return <ErrorState message={indexQuery.error} />
  if (!indexQuery.data) return null

  const routeFares = indexQuery.data.route_fares
  const cities = new Set<string>()
  Object.keys(routeFares).forEach((r) => {
    const [o, d] = r.split('-')
    cities.add(o)
    cities.add(d)
  })
  const cityList = Array.from(cities).sort()

  if (cityList.length === 0) {
    return <EmptyState message="No route data available to build a heatmap yet." />
  }

  return (
    <div>
      <Card>
        <div className="overflow-x-auto">
          <table className="text-xs border-collapse">
            <thead>
              <tr>
                <th className="p-2"></th>
                {cityList.map((c) => (
                  <th key={c} className="p-2 font-semibold text-muted">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cityList.map((origin) => (
                <tr key={origin}>
                  <td className="p-2 font-semibold text-muted">{origin}</td>
                  {cityList.map((dest) => {
                    if (origin === dest) return <td key={dest} className="p-2 bg-slate-50" />
                    const forward = routeFares[`${origin}-${dest}`]
                    const backward = routeFares[`${dest}-${origin}`]
                    const detail = forward ?? backward
                    if (!detail) return <td key={dest} className="p-2 bg-slate-50 text-center text-slate-300">{'\u00b7'}</td>
                    const changePct = (detail.relative - 1) * 100
                    return (
                      <td
                        key={dest}
                        className="p-2 text-center font-medium rounded"
                        style={{ backgroundColor: colorForChange(changePct) }}
                        title={`${origin}-${dest}: ${changePct.toFixed(2)}%`}
                      >
                        {changePct.toFixed(1)}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-2 mt-4 text-xs text-muted">
          <span>Cheaper</span>
          <div className="h-2 w-32 rounded" style={{ background: 'linear-gradient(to right, rgba(22,163,74,0.77), white, rgba(220,38,38,0.77))' }} />
          <span>More expensive</span>
        </div>
      </Card>
    </div>
  )
}

function colorForChange(pct: number): string {
  const clamped = Math.max(-15, Math.min(15, pct))
  if (clamped >= 0) {
    const intensity = clamped / 15
    return `rgba(220, 38, 38, ${0.12 + intensity * 0.65})`
  }
  const intensity = -clamped / 15
  return `rgba(22, 163, 74, ${0.12 + intensity * 0.65})`
}
