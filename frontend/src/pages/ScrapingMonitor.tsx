import { useState } from 'react'
import { useApiQuery } from '../hooks/useApiQuery'
import { api } from '../api/client'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import type { IngestionRunRow } from '../types'

const STATUS_STYLES: Record<string, string> = {
  SUCCESS: 'bg-emerald-100 text-emerald-800',
  RUNNING: 'bg-blue-100 text-blue-800',
  SOURCE_UNAVAILABLE: 'bg-amber-100 text-amber-800',
  FAILED: 'bg-red-100 text-red-800',
}

export default function ScrapingMonitor() {
  const runsQuery = useApiQuery<IngestionRunRow[]>('/scraping/runs')
  const [triggering, setTriggering] = useState(false)
  const [triggerResult, setTriggerResult] = useState<string | null>(null)

  const handleTrigger = async () => {
    setTriggering(true)
    setTriggerResult(null)
    try {
      const result = await api.post<{ runs: Array<{ source: string; status: string }> }>('/scraping/trigger', {})
      setTriggerResult(
        result.runs.map((r) => `${r.source}: ${r.status}`).join(' · ') || 'No active sources to trigger.',
      )
      runsQuery.refetch()
    } catch (err) {
      setTriggerResult(`Trigger failed: ${(err as Error).message}`)
    } finally {
      setTriggering(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Collection Monitor"
        subtitle="Ingestion run history across all configured data sources"
        action={
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded disabled:opacity-50"
          >
            {triggering ? 'Triggering…' : 'Trigger ingestion now'}
          </button>
        }
      />

      {triggerResult && (
        <div className="text-sm bg-blue-50 border border-blue-200 text-blue-800 rounded-lg p-3 mb-4">
          {triggerResult}
        </div>
      )}

      <Card>
        {runsQuery.loading && <LoadingState />}
        {runsQuery.error && <ErrorState message={runsQuery.error} />}
        {runsQuery.data && runsQuery.data.length === 0 && <EmptyState message="No ingestion runs recorded yet." />}
        {runsQuery.data && runsQuery.data.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-slate-200">
                <th className="py-2">Started</th>
                <th className="py-2">Status</th>
                <th className="py-2 text-right">Rows collected</th>
                <th className="py-2 text-right">Rows valid</th>
                <th className="py-2">Error</th>
              </tr>
            </thead>
            <tbody>
              {runsQuery.data.map((run) => (
                <tr key={run.id} className="border-b border-slate-100">
                  <td className="py-2">{new Date(run.started_at).toLocaleString()}</td>
                  <td className="py-2">
                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${STATUS_STYLES[run.status] ?? 'bg-slate-100'}`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="py-2 text-right">{run.rows_collected.toLocaleString()}</td>
                  <td className="py-2 text-right">{run.rows_valid.toLocaleString()}</td>
                  <td className="py-2 text-muted text-xs">{run.error_message ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <p className="text-xs text-muted mt-4">
        A source that fails or is unreachable shows SOURCE UNAVAILABLE for that run rather than fabricating
        data, and never crashes the rest of the ingestion pipeline.
      </p>
    </div>
  )
}
