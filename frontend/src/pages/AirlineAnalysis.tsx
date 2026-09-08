import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import type { IndexResult } from '../types'

interface AirlineRow {
  airline: string
  valid_observations: number
  median_fare: number
  observation_share_pct: number
}

export default function AirlineAnalysis() {
  const airlinesQuery = useApiQuery<{ airlines: AirlineRow[] }>('/analytics/airlines')
  const indexQuery = useApiQuery<IndexResult>('/index/current')

  if (airlinesQuery.loading) return <LoadingState label="Loading airline analysis…" />
  if (airlinesQuery.error) return <ErrorState message={airlinesQuery.error} />

  const airlines = airlinesQuery.data?.airlines ?? []
  const contributions = indexQuery.data?.airline_contributions ?? {}

  if (airlines.length === 0) return <EmptyState message="No airline data available yet." />

  return (
    <div>
      <PageHeader title="Airline Analysis" subtitle="Fare levels and index contribution by airline" />

      <Card title="Median fare by airline" className="mb-6">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={airlines}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="airline" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v: number) => `₹${v.toLocaleString()}`} />
            <Bar dataKey="median_fare" fill="#1d4ed8" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Airline comparison table">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted border-b border-slate-200">
              <th className="py-2">Airline</th>
              <th className="py-2 text-right">Valid observations</th>
              <th className="py-2 text-right">Observation share</th>
              <th className="py-2 text-right">Median fare</th>
              <th className="py-2 text-right">Index contribution</th>
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
                  <td className="py-2 text-right">₹{a.median_fare.toLocaleString()}</td>
                  <td className={`py-2 text-right font-medium ${contrib !== undefined ? (contrib >= 0 ? 'text-red-600' : 'text-emerald-600') : 'text-muted'}`}>
                    {contrib !== undefined ? contrib.toFixed(3) : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="text-xs text-muted mt-3">
          Index contribution is a transparency proxy weighted by each airline's observed share of valid
          fare quotes in the current period — not a claim of official passenger market share.
        </p>
      </Card>
    </div>
  )
}
