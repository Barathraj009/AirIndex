import { useState } from 'react'
import { useApiQuery } from '../hooks/useApiQuery'
import { api } from '../api/client'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import { TabBar } from '../components/Tabs'
import type { Route, AuditLogRow, DataSourceItem, UserItem, IndexConfigItem } from '../types'

type AdminTab = 'routes' | 'sources' | 'users' | 'config' | 'audit'

export default function Admin() {
  const [activeTab, setActiveTab] = useState<AdminTab>('routes')

  return (
    <div>
      <PageHeader title="Administration" subtitle="Route weights, data sources, users, and index config" />
      <TabBar
        tabs={[
          { key: 'routes', label: 'Route Weights' },
          { key: 'sources', label: 'Data Sources' },
          { key: 'users', label: 'Users' },
          { key: 'config', label: 'Index Config' },
          { key: 'audit', label: 'Audit Log' },
        ]}
        active={activeTab}
        onChange={(k) => setActiveTab(k as AdminTab)}
      />

      <div key={activeTab} className="animate-fade-in-up">
        {activeTab === 'routes' && <RoutesTab />}
        {activeTab === 'sources' && <SourcesTab />}
        {activeTab === 'users' && <UsersTab />}
        {activeTab === 'config' && <ConfigTab />}
        {activeTab === 'audit' && <AuditTab />}
      </div>
    </div>
  )
}

const inputCls =
  'w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink placeholder:text-slate-600 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/60 focus:border-brand-500/50'

function RoutesTab() {
  const routesQuery = useApiQuery<Route[]>('/routes')
  const auditQuery = useApiQuery<AuditLogRow[]>('/admin/audit-log')
  const [editingRouteId, setEditingRouteId] = useState<number | null>(null)
  const [draftWeight, setDraftWeight] = useState('')
  const [calibrateStatus, setCalibrateStatus] = useState<string | null>(null)
  const [routeError, setRouteError] = useState<string | null>(null)

  const saveWeight = async (routeId: number) => {
    const weight = parseFloat(draftWeight)
    if (Number.isNaN(weight) || weight < 0 || weight > 1) {
      setRouteError('Weight must be 0\u20131.')
      return
    }
    try {
      await api.patch(`/routes/${routeId}/weight`, { weight })
      setEditingRouteId(null)
      setRouteError(null)
      routesQuery.refetch()
    } catch (err) {
      setRouteError((err as Error).message)
    }
  }

  const handleCalibrateDGCA = async () => {
    setCalibrateStatus('Calibrating with DGCA traffic data…')
    try {
      await api.post('/admin/calibrate-weights-dgca', {})
      setCalibrateStatus('Calibrated successfully.')
      routesQuery.refetch()
      auditQuery.refetch()
      setTimeout(() => setCalibrateStatus(null), 5000)
    } catch (err) {
      setCalibrateStatus(`Failed: ${(err as Error).message}`)
    }
  }

  return (
    <Card title="Route basket weights">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
        <p className="text-xs text-muted max-w-xl">
          Route weights define the basket composition for the Laspeyres index.
        </p>
        <button
          onClick={handleCalibrateDGCA}
          className="text-xs rounded-lg bg-brand-500/15 border border-brand-500/40 px-3 py-1.5 font-semibold text-brand-200 transition-colors hover:bg-brand-500/25"
        >
          {calibrateStatus ? calibrateStatus : 'Calibrate with DGCA'}
        </button>
      </div>
      {calibrateStatus && (
        <p className="mb-4 rounded-lg border border-brand-500/25 bg-brand-500/10 px-3 py-2 text-xs text-brand-200">{calibrateStatus}</p>
      )}
      {routesQuery.loading && <LoadingState />}
      {routesQuery.error && <ErrorState message={routesQuery.error} onRetry={routesQuery.refetch} />}
      {routesQuery.data && (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-line bg-raised/60">
                <th className="py-2.5 px-3 font-medium">Route</th>
                <th className="py-2.5 px-3 font-medium">Tier</th>
                <th className="py-2.5 px-3 text-right font-medium">Weight</th>
                <th className="py-2.5 px-3 text-right font-medium">Status</th>
                <th className="py-2.5 px-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {routesQuery.data.map((r) => (
                <tr key={r.id} className="border-b border-lineSoft hover:bg-raised/40 transition-colors">
                  <td className="py-2.5 px-3 font-medium text-ink">
                    <span className="rounded-md bg-brand-500/10 px-2 py-0.5 font-mono text-xs text-brand-300">
                      {r.origin}-{r.destination}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-xs text-muted">{r.distance_tier ?? '\u2014'}</td>
                  <td className="py-2.5 px-3 text-right">
                    {editingRouteId === r.id ? (
                      <input
                        type="number"
                        step="0.001"
                        min={0}
                        max={1}
                        value={draftWeight}
                        onChange={(e) => setDraftWeight(e.target.value)}
                        className={`${inputCls} w-24 text-right`}
                      />
                    ) : (
                      <span className="font-mono text-ink tabular-nums">{(r.weight * 100).toFixed(2)}%</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${r.active ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-500/15 text-slate-400'}`}>
                      {r.active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    {editingRouteId === r.id ? (
                      <div className="space-x-2 text-xs">
                        <button onClick={() => saveWeight(r.id)} className="font-semibold text-brand-400 hover:text-brand-300">Save</button>
                        <button onClick={() => setEditingRouteId(null)} className="text-muted hover:text-slate-300">Cancel</button>
                      </div>
                    ) : (
                      <button
                        onClick={() => {
                          setEditingRouteId(r.id)
                          setDraftWeight(String(r.weight))
                          setRouteError(null)
                        }}
                        className="text-xs font-medium text-brand-400 hover:text-brand-300 hover:underline"
                      >
                        Edit Weight
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {routeError && <p className="mt-2 text-xs text-rose-400">{routeError}</p>}
    </Card>
  )
}

function SourcesTab() {
  const sourcesQuery = useApiQuery<DataSourceItem[]>('/admin/data-sources')
  const [error, setError] = useState<string | null>(null)

  const toggleSource = async (sourceId: number) => {
    setError(null)
    try {
      await api.patch(`/admin/data-sources/${sourceId}/toggle`, {})
      sourcesQuery.refetch()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <Card title="Ingestion Data Sources">
      <p className="text-xs text-muted pb-4">
        Manage active scraping adapters and public data collection endpoints.
      </p>
      {error && <p className="mb-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>}
      {sourcesQuery.loading && <LoadingState />}
      {sourcesQuery.error && <ErrorState message={sourcesQuery.error} onRetry={sourcesQuery.refetch} />}
      {sourcesQuery.data && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {sourcesQuery.data.map((src) => (
            <div key={src.id} className="flex flex-col justify-between rounded-xl border border-line bg-raised p-4 shadow-card">
              <div>
                <div className="mb-2 flex items-start justify-between">
                  <h4 className="text-sm font-semibold text-ink">{src.name}</h4>
                  <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${src.active ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-500/15 text-slate-400'}`}>
                    {src.active ? 'ACTIVE' : 'DISABLED'}
                  </span>
                </div>
                <p className="mb-2 text-xs text-muted">Type: <span className="font-mono text-slate-300">{src.source_type}</span></p>
                {src.last_success_at && (
                  <p className="text-xs text-muted">Last success: {new Date(src.last_success_at).toLocaleString()}</p>
                )}
                {src.last_failure_reason && (
                  <p className="mt-2 rounded-md border border-amber-500/25 bg-amber-500/10 p-1.5 text-xs text-amber-200">
                    {src.last_failure_reason}
                  </p>
                )}
              </div>
              <div className="mt-4 flex justify-end border-t border-lineSoft pt-3">
                <button
                  onClick={() => toggleSource(src.id)}
                  className={`text-xs rounded-lg px-3 py-1.5 font-medium transition-colors ${
                    src.active
                      ? 'border border-rose-500/40 text-rose-300 hover:bg-rose-500/10'
                      : 'border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10'
                  }`}
                >
                  {src.active ? 'Disable' : 'Enable'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function UsersTab() {
  const usersQuery = useApiQuery<UserItem[]>('/admin/users')
  const auditQuery = useApiQuery<AuditLogRow[]>('/admin/audit-log')
  const [showNewUser, setShowNewUser] = useState(false)
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<'ADMIN' | 'ANALYST' | 'VIEWER'>('ANALYST')
  const [userFormError, setUserFormError] = useState<string | null>(null)
  const [userFormSuccess, setUserFormSuccess] = useState<string | null>(null)

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    setUserFormError(null)
    setUserFormSuccess(null)
    try {
      await api.post('/admin/users', { email: newEmail, password: newPassword, role: newRole })
      setUserFormSuccess(`User ${newEmail} created.`)
      setNewEmail('')
      setNewPassword('')
      usersQuery.refetch()
      auditQuery.refetch()
      setTimeout(() => { setShowNewUser(false); setUserFormSuccess(null) }, 2000)
    } catch (err) {
      setUserFormError((err as Error).message)
    }
  }

  const toggleUserActive = async (userId: number) => {
    setUserFormError(null)
    try {
      await api.patch(`/admin/users/${userId}/toggle-active`, {})
      usersQuery.refetch()
    } catch (err) {
      setUserFormError((err as Error).message)
    }
  }

  const handleRoleChange = async (userId: number, role: string) => {
    setUserFormError(null)
    try {
      await api.patch(`/admin/users/${userId}/role`, { role })
      usersQuery.refetch()
    } catch (err) {
      setUserFormError((err as Error).message)
    }
  }

  return (
    <Card title="User Accounts & Roles">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
        <p className="text-xs text-muted">ADMIN, ANALYST, VIEWER roles.</p>
        <button
          onClick={() => setShowNewUser(!showNewUser)}
          className="text-xs rounded-lg bg-brand-500/15 border border-brand-500/40 px-3 py-1.5 font-semibold text-brand-200 transition-colors hover:bg-brand-500/25"
        >
          {showNewUser ? 'Cancel' : '+ Add User'}
        </button>
      </div>

      {showNewUser && (
        <form onSubmit={handleCreateUser} className="mb-6 rounded-xl border border-line bg-raised p-4 text-sm">
          <div className="mb-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted">Email</span>
              <input type="email" required value={newEmail} onChange={(e) => setNewEmail(e.target.value)} className={inputCls} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted">Password</span>
              <input type="password" required minLength={6} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className={inputCls} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted">Role</span>
              <select value={newRole} onChange={(e) => setNewRole(e.target.value as 'ADMIN' | 'ANALYST' | 'VIEWER')} className={inputCls}>
                <option value="VIEWER">VIEWER</option>
                <option value="ANALYST">ANALYST</option>
                <option value="ADMIN">ADMIN</option>
              </select>
            </label>
          </div>
          {userFormError && <p className="mb-2 text-xs text-rose-400">{userFormError}</p>}
          {userFormSuccess && <p className="mb-2 text-xs text-emerald-400">{userFormSuccess}</p>}
          <button type="submit" className="rounded-lg bg-brand-gradient px-4 py-1.5 text-xs font-semibold text-white">Save User</button>
        </form>
      )}

      {userFormError && !showNewUser && <p className="mb-3 text-xs text-rose-400">{userFormError}</p>}

      {usersQuery.loading && <LoadingState />}
      {usersQuery.error && <ErrorState message={usersQuery.error} onRetry={usersQuery.refetch} />}
      {usersQuery.data && (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted border-b border-line bg-raised/60">
                <th className="py-2.5 px-3 font-medium">Email</th>
                <th className="py-2.5 px-3 font-medium">Role</th>
                <th className="py-2.5 px-3 text-center font-medium">Status</th>
                <th className="py-2.5 px-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {usersQuery.data.map((u) => (
                <tr key={u.id} className="border-b border-lineSoft hover:bg-raised/40 transition-colors">
                  <td className="py-2.5 px-3 font-medium text-ink">{u.email}</td>
                  <td className="py-2.5 px-3">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      className="rounded-lg border border-line bg-raised px-2 py-1 text-xs font-medium text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/60"
                    >
                      <option value="ADMIN">ADMIN</option>
                      <option value="ANALYST">ANALYST</option>
                      <option value="VIEWER">VIEWER</option>
                    </select>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${u.is_active ? 'bg-emerald-500/15 text-emerald-300' : 'bg-rose-500/15 text-rose-300'}`}>
                      {u.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <button
                      onClick={() => toggleUserActive(u.id)}
                      className="text-xs underline text-slate-400 hover:text-slate-200"
                    >
                      {u.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function ConfigTab() {
  const activeConfigQuery = useApiQuery<IndexConfigItem>('/index/config/current')
  const configHistoryQuery = useApiQuery<IndexConfigItem[]>('/index/config/history')
  const auditQuery = useApiQuery<AuditLogRow[]>('/admin/audit-log')
  const [showNewConfig, setShowNewConfig] = useState(false)
  const [configBasePeriod, setConfigBasePeriod] = useState('2026-01')
  const [configIncludeSuspicious, setConfigIncludeSuspicious] = useState(false)
  const [configNotes, setConfigNotes] = useState('')
  const [configError, setConfigError] = useState<string | null>(null)
  const [configSuccess, setConfigSuccess] = useState<string | null>(null)

  const handleCreateConfig = async (e: React.FormEvent) => {
    e.preventDefault()
    setConfigError(null)
    setConfigSuccess(null)
    try {
      await api.post('/index/config', {
        base_period: configBasePeriod,
        include_suspicious: configIncludeSuspicious,
        notes: configNotes || undefined,
      })
      setConfigSuccess(`Configuration with base ${configBasePeriod} activated.`)
      activeConfigQuery.refetch()
      configHistoryQuery.refetch()
      auditQuery.refetch()
      setTimeout(() => { setShowNewConfig(false); setConfigSuccess(null) }, 2000)
    } catch (err) {
      setConfigError((err as Error).message)
    }
  }

  return (
    <Card title="Index Configuration">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
        <p className="text-xs text-muted max-w-xl">Configure active Laspeyres baseline parameters.</p>
        <button
          onClick={() => setShowNewConfig(!showNewConfig)}
          className="text-xs rounded-lg bg-brand-500/15 border border-brand-500/40 px-3 py-1.5 font-semibold text-brand-200 transition-colors hover:bg-brand-500/25"
        >
          {showNewConfig ? 'Cancel' : '+ New Config'}
        </button>
      </div>

      {showNewConfig && (
        <form onSubmit={handleCreateConfig} className="mb-6 rounded-xl border border-line bg-raised p-4 text-sm">
          <div className="mb-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted">Base Period (YYYY-MM)</span>
              <input type="month" required value={configBasePeriod} onChange={(e) => setConfigBasePeriod(e.target.value)} className={inputCls} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted">Include Suspicious</span>
              <div className="flex items-center gap-2 pt-2">
                <input type="checkbox" checked={configIncludeSuspicious} onChange={(e) => setConfigIncludeSuspicious(e.target.checked)} className="rounded" />
                <span className="text-xs text-slate-300">Include SUSPICIOUS rows</span>
              </div>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-muted">Notes</span>
              <input type="text" value={configNotes} onChange={(e) => setConfigNotes(e.target.value)} placeholder="e.g. Q2 2026 baseline" className={inputCls} />
            </label>
          </div>
          {configError && <p className="mb-2 text-xs text-rose-400">{configError}</p>}
          {configSuccess && <p className="mb-2 text-xs text-emerald-400">{configSuccess}</p>}
          <button type="submit" className="rounded-lg bg-brand-gradient px-4 py-1.5 text-xs font-semibold text-white">Activate</button>
        </form>
      )}

      {activeConfigQuery.data && (
        <div className="mb-6 rounded-xl border border-brand-500/25 bg-brand-500/10 p-4 text-xs">
          <h4 className="mb-2 text-sm font-bold text-brand-200">Active Configuration</h4>
          <div className="grid grid-cols-2 gap-3 text-slate-300 md:grid-cols-4">
            <div><span className="text-muted">Base: </span><strong className="font-mono text-brand-200">{activeConfigQuery.data.base_period}</strong></div>
            <div><span className="text-muted">Methodology: </span><strong>{activeConfigQuery.data.methodology_version}</strong></div>
            <div><span className="text-muted">Created by: </span><strong>{activeConfigQuery.data.created_by ?? 'System'}</strong></div>
            <div><span className="text-muted">Suspicious: </span><strong>{activeConfigQuery.data.include_suspicious ? 'Included' : 'Excluded'}</strong></div>
          </div>
        </div>
      )}

      <h4 className="mb-2 text-sm font-semibold text-ink">Configuration History</h4>
      {configHistoryQuery.data && (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-muted border-b border-line bg-raised/60">
                <th className="py-2.5 px-3 font-medium">Deployed</th>
                <th className="py-2.5 px-3 font-medium">Base Period</th>
                <th className="py-2.5 px-3 font-medium">Author</th>
                <th className="py-2.5 px-3 font-medium">Status</th>
                <th className="py-2.5 px-3 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody>
              {configHistoryQuery.data.map((c) => (
                <tr key={c.id} className="border-b border-lineSoft hover:bg-raised/40">
                  <td className="py-2.5 px-3 text-slate-300">{new Date(c.created_at).toLocaleString()}</td>
                  <td className="py-2.5 px-3 font-mono font-semibold text-ink">{c.base_period}</td>
                  <td className="py-2.5 px-3 text-slate-300">{c.created_by ?? 'seed'}</td>
                  <td className="py-2.5 px-3">
                    <span className={`px-2 py-0.5 rounded-full font-bold ${c.is_active ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-500/15 text-slate-400'}`}>
                      {c.is_active ? 'ACTIVE' : 'SUPERSEDED'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-muted">{c.notes ?? '\u2014'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function AuditTab() {
  const auditQuery = useApiQuery<AuditLogRow[]>('/admin/audit-log')

  return (
    <Card title="System Audit Trail">
      {auditQuery.loading && <LoadingState />}
      {auditQuery.error && <ErrorState message={auditQuery.error} onRetry={auditQuery.refetch} />}
      {auditQuery.data && auditQuery.data.length === 0 && <EmptyState message="No administrative actions recorded yet." />}
      {auditQuery.data && auditQuery.data.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-muted border-b border-line bg-raised/60">
                <th className="py-2.5 px-3 font-medium">Timestamp</th>
                <th className="py-2.5 px-3 font-medium">User</th>
                <th className="py-2.5 px-3 font-medium">Action</th>
                <th className="py-2.5 px-3 font-medium">Target</th>
                <th className="py-2.5 px-3 font-medium">Details</th>
              </tr>
            </thead>
            <tbody>
              {auditQuery.data.map((entry) => (
                <tr key={entry.id} className="border-b border-lineSoft hover:bg-raised/40">
                  <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300">{new Date(entry.timestamp).toLocaleString()}</td>
                  <td className="py-2.5 px-3 font-medium text-ink">{entry.user_email ?? 'System'}</td>
                  <td className="py-2.5 px-3 font-mono text-[11px] font-semibold text-brand-300">{entry.action}</td>
                  <td className="py-2.5 px-3 text-muted">
                    {entry.entity_type ? `${entry.entity_type}${entry.entity_id ? ` #${entry.entity_id}` : ''}` : '\u2014'}
                  </td>
                  <td className="py-2.5 px-3 max-w-xs truncate font-mono text-[10px] text-slate-500">
                    {entry.details ? JSON.stringify(entry.details) : '\u2014'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}