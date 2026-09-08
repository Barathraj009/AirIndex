import { useApiQuery } from '../hooks/useApiQuery'
import { PageHeader, Card, StatCard, LoadingState, ErrorState } from '../components/ui'
import type { DataQualitySummary } from '../types'

export default function DataQuality() {
  const quality = useApiQuery<DataQualitySummary>('/data-quality/summary')

  if (quality.loading) return <LoadingState label="Loading data quality report…" />
  if (quality.error) return <ErrorState message={quality.error} />
  if (!quality.data) return null

  const d = quality.data

  return (
    <div>
      <PageHeader title="Data Quality" subtitle="Validation, deduplication, and outlier-detection results" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total observations" value={d.total_rows.toLocaleString()} />
        <StatCard label="Valid" value={d.valid.toLocaleString()} sub={`${d.valid_pct}%`} tone="down" />
        <StatCard label="Suspicious (outlier)" value={d.suspicious.toLocaleString()} />
        <StatCard label="Invalid / unavailable" value={(d.invalid + d.unavailable).toLocaleString()} tone="up" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <Card title="Outlier detection">
          <Row label="Flagged by IQR method" value={d.outliers_iqr} />
          <Row label="Flagged by MAD method" value={d.outliers_mad} />
          <p className="text-xs text-muted mt-3">
            Outliers are detected within each route/booking-window group (fares differ hugely by route, so a
            global threshold would be meaningless). A row is SUSPICIOUS if either the IQR or MAD test flags
            it.
          </p>
        </Card>
        <Card title="Deduplication">
          <Row label="Duplicate observations removed" value={d.duplicates_removed} />
          <p className="text-xs text-muted mt-3">
            Deduplication uses a stable hash of route, airline, flight number, travel date, collection
            timestamp, fare class, and fare — the same underlying quote is never double-counted.
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
