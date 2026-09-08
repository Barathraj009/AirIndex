import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import type { Route } from '../types'

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

export default function LeadTimeAnalysis() {
  const routesQuery = useApiQuery<Route[]>('/routes')
  const rankingQuery = useApiQuery<RouteRanking>('/analytics/lead-time/all-routes-summary')

  const routes = routesQuery.data ?? []
  const [selectedRoute, setSelectedRoute] = useState<string>('')

  const activeRoute = selectedRoute || (routes[0] ? `${routes[0].origin}-${routes[0].destination}` : '')
  const [origin, destination] = activeRoute ? activeRoute.split('-') : ['', '']

  const leadTimeQuery = useApiQuery<LeadTimeResponse>(
    origin && destination ? `/analytics/lead-time?origin=${origin}&destination=${destination}` : null,
    [origin, destination],
  )

  return (
    <div>
      <PageHeader title="Lead-Time Analysis" subtitle="How fares change depending on how early a ticket is booked" />

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
                <Tooltip labelFormatter={(v) => `T+${v}`} formatter={(v: number) => [`₹${v.toLocaleString()}`, 'Median fare']} />
                <Line type="monotone" dataKey="median_fare" stroke="#1d4ed8" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
            {leadTimeQuery.data.pct_increase_last_minute_vs_cheapest !== null && (
              <p className="text-sm text-muted mt-2">
                Booking at the last minute (T+1) costs{' '}
                <span className="font-semibold text-red-600">
                  {leadTimeQuery.data.pct_increase_last_minute_vs_cheapest.toFixed(1)}%
                </span>{' '}
                more than the cheapest booking window on this route.
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
