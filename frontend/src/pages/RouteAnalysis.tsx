import { useMemo, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Cell } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState } from '../components/ui'
import type { IndexResult, Route } from '../types'

export default function RouteAnalysis() {
  const routesQuery = useApiQuery<Route[]>('/routes')
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

  if (indexQuery.loading || routesQuery.loading) return <LoadingState label="Loading route analysis…" />
  if (indexQuery.error) return <ErrorState message={indexQuery.error} />
  if (!indexQuery.data) return null

  const detail = selected ? indexQuery.data.route_fares[selected] : null

  return (
    <div>
      <PageHeader title="Route Analysis" subtitle="Fare change by route, base vs current period" />

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
        <Card title={`Route detail — ${selected}`}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <Detail label="Weight" value={`${(detail.weight * 100).toFixed(1)}%`} />
            <Detail label="Base period fare" value={`₹${detail.base_period_fare.toLocaleString()}`} />
            <Detail label="Current period fare" value={`₹${detail.as_of_period_fare.toLocaleString()}`} />
            <Detail label="Price relative" value={detail.relative.toFixed(3)} />
          </div>
        </Card>
      )}

      <Card title="All tracked routes" className="mt-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted border-b border-slate-200">
              <th className="py-2">Route</th>
              <th className="py-2">Tier</th>
              <th className="py-2 text-right">Weight</th>
              <th className="py-2 text-right">Active</th>
            </tr>
          </thead>
          <tbody>
            {(routesQuery.data ?? []).map((r) => (
              <tr key={r.id} className="border-b border-slate-100">
                <td className="py-2 font-medium">
                  {r.origin}-{r.destination}
                </td>
                <td className="py-2 text-muted">{r.distance_tier ?? '—'}</td>
                <td className="py-2 text-right">{(r.weight * 100).toFixed(1)}%</td>
                <td className="py-2 text-right">{r.active ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted uppercase">{label}</div>
      <div className="font-semibold text-ink">{value}</div>
    </div>
  )
}
