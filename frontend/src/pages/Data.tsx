import { useState } from 'react'
import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, StatCard, LoadingState, ErrorState, EmptyState, SourceBadge, QualityBadge } from '../components/ui'
import type { FareObservation, Route, Airline, DataQualitySummary } from '../types'

type DataTab = 'explorer' | 'quality'

const TABS: { key: DataTab; label: string }[] = [
  { key: 'explorer', label: 'Explorer' },
  { key: 'quality', label: 'Quality' },
]

export default function Data() {
  const [tab, setTab] = useState<DataTab>('explorer')

  return (
    <div>
      <PageHeader title="Data" subtitle="Browse observations and quality metrics" />
      <TabBar tabs={TABS} active={tab} onChange={setTab} />
      {tab === 'explorer' && <ExplorerTab />}
      {tab === 'quality' && <QualityTab />}
    </div>
  )
}

function ExplorerTab() {
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
            label="Quality"
            value={qualityStatus}
            onChange={setQualityStatus}
            options={['VALID', 'SUSPICIOUS', 'INVALID', 'UNAVAILABLE']}
          />
          <div className="flex items-end">
            <a
              href={`/api/exports/fares.csv${params.toString() ? `?${params.toString()}` : ''}`}
              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded font-medium hover:bg-blue-700"
            >
              Export CSV
            </a>
          </div>
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
                    <td className="py-1.5 pr-3">{f.booking_window_days !== null ? `T+${f.booking_window_days}` : '\u2014'}</td>
                    <td className="py-1.5 pr-3 text-right">{f.total_fare ? `\u20b9${f.total_fare.toLocaleString()}` : '\u2014'}</td>
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

function QualityTab() {
  const quality = useApiQuery<DataQualitySummary>('/data-quality/summary')

  if (quality.loading) return <LoadingState label="Loading quality report..." />
  if (quality.error) return <ErrorState message={quality.error} />
  if (!quality.data) return null

  const d = quality.data

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total observations" value={d.total_rows.toLocaleString()} />
        <StatCard label="Valid" value={d.valid.toLocaleString()} sub={`${d.valid_pct}%`} tone="down" />
        <StatCard label="Suspicious" value={d.suspicious.toLocaleString()} />
        <StatCard label="Invalid / unavailable" value={(d.invalid + d.unavailable).toLocaleString()} tone="up" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <Card title="Outlier detection">
          <Row label="Flagged by IQR" value={d.outliers_iqr} />
          <Row label="Flagged by MAD" value={d.outliers_mad} />
          <p className="text-xs text-muted mt-3">
            Outliers detected within each route/booking-window group.
            A row is SUSPICIOUS if either test flags it.
          </p>
        </Card>
        <Card title="Deduplication">
          <Row label="Duplicates removed" value={d.duplicates_removed} />
          <p className="text-xs text-muted mt-3">
            Deduplication uses a stable hash of route, airline, flight number, travel date,
            collection timestamp, fare class, and fare.
          </p>
        </Card>
      </div>

      <Card title="Sample of flagged issues">
        {d.issues_sample.length === 0 ? (
          <p className="text-sm text-muted">No issues flagged.</p>
        ) : (
          <ul className="text-sm text-slate-700 space-y-1">
            {d.issues_sample.map((issue, i) => (
              <li key={i} className="font-mono text-xs bg-slate-50 border border-slate-200 rounded px-2 py-1">
                {issue}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

function Row({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between text-sm py-1">
      <span className="text-muted">{label}</span>
      <span className="font-semibold">{value.toLocaleString()}</span>
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

function TabBar({ tabs, active, onChange }: { tabs: { key: string; label: string }[]; active: string; onChange: (k: any) => void }) {
  return (
    <div className="flex border-b border-slate-200 mb-6">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            active === t.key
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
