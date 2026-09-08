import { useState } from 'react'
import { useApiQuery } from '../hooks/useApiQuery'
import { api } from '../api/client'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import type { Route, AuditLogRow } from '../types'

export default function Admin() {
  const routesQuery = useApiQuery<Route[]>('/routes')
  const auditQuery = useApiQuery<AuditLogRow[]>('/admin/audit-log')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [draftWeight, setDraftWeight] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)

  const startEdit = (route: Route) => {
    setEditingId(route.id)
    setDraftWeight(String(route.weight))
    setSaveError(null)
  }

  const saveWeight = async (routeId: number) => {
    const weight = parseFloat(draftWeight)
    if (Number.isNaN(weight) || weight < 0 || weight > 1) {
      setSaveError('Weight must be a number between 0 and 1.')
      return
    }
    try {
      await api.patch(`/routes/${routeId}/weight`, { weight })
      setEditingId(null)
      routesQuery.refetch()
    } catch (err) {
      setSaveError((err as Error).message)
    }
  }

  return (
    <div>
      <PageHeader title="Administration" subtitle="Route weights, data sources, and audit log — ADMIN role required" />

      <Card title="Route weights" className="mb-6">
        <p className="text-xs text-muted mb-3">
          Changing a route's weight here does not require a code deployment — it takes effect on the next
          index calculation, per the configurable-methodology requirement.
        </p>
        {routesQuery.loading && <LoadingState />}
        {routesQuery.error && <ErrorState message={routesQuery.error} />}
        {routesQuery.data && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-slate-200">
                <th className="py-2">Route</th>
                <th className="py-2 text-right">Weight</th>
                <th className="py-2 text-right">Active</th>
                <th className="py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {routesQuery.data.map((r) => (
                <tr key={r.id} className="border-b border-slate-100">
                  <td className="py-2 font-medium">
                    {r.origin}-{r.destination}
                  </td>
                  <td className="py-2 text-right">
                    {editingId === r.id ? (
                      <input
                        type="number"
                        step="0.01"
                        min={0}
                        max={1}
                        value={draftWeight}
                        onChange={(e) => setDraftWeight(e.target.value)}
                        className="border border-slate-300 rounded px-2 py-0.5 w-20 text-right"
                      />
                    ) : (
                      `${(r.weight * 100).toFixed(1)}%`
                    )}
                  </td>
                  <td className="py-2 text-right">{r.active ? 'Yes' : 'No'}</td>
                  <td className="py-2 text-right">
                    {editingId === r.id ? (
                      <>
                        <button onClick={() => saveWeight(r.id)} className="text-blue-600 font-medium mr-2">
                          Save
                        </button>
                        <button onClick={() => setEditingId(null)} className="text-muted">
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button onClick={() => startEdit(r)} className="text-blue-600 font-medium">
                        Edit
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {saveError && <p className="text-xs text-red-600 mt-2">{saveError}</p>}
      </Card>

      <Card title="Audit log">
        {auditQuery.loading && <LoadingState />}
        {auditQuery.data && auditQuery.data.length === 0 && <EmptyState message="No administrative actions recorded yet." />}
        {auditQuery.data && auditQuery.data.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-slate-200">
                <th className="py-2">Timestamp</th>
                <th className="py-2">User</th>
                <th className="py-2">Action</th>
                <th className="py-2">Entity</th>
              </tr>
            </thead>
            <tbody>
              {auditQuery.data.map((entry) => (
                <tr key={entry.id} className="border-b border-slate-100">
                  <td className="py-2 text-xs">{new Date(entry.timestamp).toLocaleString()}</td>
                  <td className="py-2">{entry.user_email ?? '—'}</td>
                  <td className="py-2 font-mono text-xs">{entry.action}</td>
                  <td className="py-2 text-muted text-xs">
                    {entry.entity_type ? `${entry.entity_type}${entry.entity_id ? ` #${entry.entity_id}` : ''}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
