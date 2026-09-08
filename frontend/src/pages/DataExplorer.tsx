import { useState } from 'react'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState, SourceBadge, QualityBadge } from '../components/ui'
import type { FareObservation, Route, Airline } from '../types'

export default function DataExplorer() {
  const routesQuery = useApiQuery<Route[]>('/routes')
  const airlinesQuery = useApiQuery<Airline[]>('/airlines')

  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [airline, setAirline] = useState('')
  const [qualityStatus, setQualityStatus] = useState('')

  const params = new URLSearchParams()
  if (origin) params.set('origin', origin)
  if (destination) params.set('destination', destination)
  if (airline) params.set('airline', airline)
  if (qualityStatus) params.set('data_quality_status', qualityStatus)
  params.set('limit', '100')

  const faresQuery = useApiQuery<FareObservation[]>(`/fares?${params.toString()}`, [origin, destination, airline, qualityStatus])

  const origins = Array.from(new Set((routesQuery.data ?? []).map((r) => r.origin))).sort()
  const destinations = Array.from(new Set((routesQuery.data ?? []).map((r) => r.destination))).sort()

  return (
    <div>
      <PageHeader
        title="Data Explorer"
        subtitle="Browse raw, normalized fare observations"
        action={
          <a
            href={`/api/exports/fares.csv${params.toString() ? `?${params.toString()}` : ''}`}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded"
          >
            Export CSV
          </a>
        }
      />

      <Card className="mb-4">
        <div className="flex flex-wrap gap-3 text-sm">
          <Select label="Origin" value={origin} onChange={setOrigin} options={origins} />
          <Select label="Destination" value={destination} onChange={setDestination} options={destinations} />
          <Select
            label="Airline"
            value={airline}
            onChange={setAirline}
            options={(airlinesQuery.data ?? []).map((a) => a.name)}
          />
          <Select
            label="Data quality"
            value={qualityStatus}
            onChange={setQualityStatus}
            options={['VALID', 'SUSPICIOUS', 'INVALID', 'UNAVAILABLE']}
          />
        </div>
      </Card>

      <Card>
        {faresQuery.loading && <LoadingState />}
        {faresQuery.error && <ErrorState message={faresQuery.error} />}
        {faresQuery.data && faresQuery.data.length === 0 && <EmptyState message="No observations match these filters." />}
        {faresQuery.data && faresQuery.data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-slate-200">
                  <th className="py-2 pr-3">Route</th>
                  <th className="py-2 pr-3">Airline</th>
                  <th className="py-2 pr-3">Travel date</th>
                  <th className="py-2 pr-3">Window</th>
                  <th className="py-2 pr-3 text-right">Fare</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Quality</th>
                  <th className="py-2 pr-3">Source</th>
                </tr>
              </thead>
              <tbody>
                {faresQuery.data.map((f) => (
                  <tr key={f.id} className="border-b border-slate-100">
                    <td className="py-1.5 pr-3 font-medium">
                      {f.origin}-{f.destination}
                    </td>
                    <td className="py-1.5 pr-3">{f.airline}</td>
                    <td className="py-1.5 pr-3">{f.travel_date}</td>
                    <td className="py-1.5 pr-3">{f.booking_window_days !== null ? `T+${f.booking_window_days}` : '—'}</td>
                    <td className="py-1.5 pr-3 text-right">{f.total_fare ? `₹${f.total_fare.toLocaleString()}` : '—'}</td>
                    <td className="py-1.5 pr-3">{f.availability_status}</td>
                    <td className="py-1.5 pr-3">
                      <QualityBadge status={f.data_quality_status} />
                    </td>
                    <td className="py-1.5 pr-3">
                      <SourceBadge sourceType={f.source_type} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: string[]
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-muted">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="border border-slate-300 rounded px-2 py-1.5 min-w-[140px]"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  )
}
