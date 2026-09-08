import { useState } from 'react'
import { useApiQuery } from '../hooks/useApiQuery'
import { api } from '../api/client'
import { PageHeader, Card, LoadingState, ErrorState, EmptyState } from '../components/ui'
import type { Route, AuditLogRow, DataSourceItem, UserItem, IndexConfigItem } from '../types'

type AdminTab = 'routes' | 'sources' | 'users' | 'config' | 'audit'

export default function Admin() {
  const [activeTab, setActiveTab] = useState<AdminTab>('routes')

  // Queries
  const routesQuery = useApiQuery<Route[]>('/routes')
  const sourcesQuery = useApiQuery<DataSourceItem[]>('/admin/data-sources')
  const usersQuery = useApiQuery<UserItem[]>('/admin/users')
  const activeConfigQuery = useApiQuery<IndexConfigItem>('/index/config/current')
  const configHistoryQuery = useApiQuery<IndexConfigItem[]>('/index/config/history')
  const auditQuery = useApiQuery<AuditLogRow[]>('/admin/audit-log')

  // Route Weight State
  const [editingRouteId, setEditingRouteId] = useState<number | null>(null)
  const [draftWeight, setDraftWeight] = useState('')
  const [calibrateStatus, setCalibrateStatus] = useState<string | null>(null)
  const [routeError, setRouteError] = useState<string | null>(null)

  // New User Form State
  const [showNewUser, setShowNewUser] = useState(false)
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<'ADMIN' | 'ANALYST' | 'VIEWER'>('ANALYST')
  const [userFormError, setUserFormError] = useState<string | null>(null)
  const [userFormSuccess, setUserFormSuccess] = useState<string | null>(null)

  // New Config Form State
  const [showNewConfig, setShowNewConfig] = useState(false)
  const [configBasePeriod, setConfigBasePeriod] = useState('2026-01')
  const [configIncludeSuspicious, setConfigIncludeSuspicious] = useState(false)
  const [configNotes, setConfigNotes] = useState('')
  const [configError, setConfigError] = useState<string | null>(null)
  const [configSuccess, setConfigSuccess] = useState<string | null>(null)

  // Route Weight Save
  const saveWeight = async (routeId: number) => {
    const weight = parseFloat(draftWeight)
    if (Number.isNaN(weight) || weight < 0 || weight > 1) {
      setRouteError('Weight must be a number between 0 and 1.')
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

  // Calibrate with DGCA Traffic
  const handleCalibrateDGCA = async () => {
    try {
      setCalibrateStatus('Calibrating route weights with DGCA passenger traffic data…')
      await api.post('/admin/calibrate-weights-dgca', {})
      setCalibrateStatus('Successfully calibrated all route weights using official DGCA domestic passenger traffic figures!')
      routesQuery.refetch()
      auditQuery.refetch()
      setTimeout(() => setCalibrateStatus(null), 5000)
    } catch (err) {
      setCalibrateStatus(`Calibration failed: ${(err as Error).message}`)
    }
  }

  // Toggle Data Source
  const toggleSource = async (sourceId: number) => {
    try {
      await api.patch(`/admin/data-sources/${sourceId}/toggle`, {})
      sourcesQuery.refetch()
      auditQuery.refetch()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  // Toggle User Active Status
  const toggleUserActive = async (userId: number) => {
    try {
      await api.patch(`/admin/users/${userId}/toggle-active`, {})
      usersQuery.refetch()
      auditQuery.refetch()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  // Change User Role
  const handleRoleChange = async (userId: number, role: string) => {
    try {
      await api.patch(`/admin/users/${userId}/role`, { role })
      usersQuery.refetch()
      auditQuery.refetch()
    } catch (err) {
      alert((err as Error).message)
    }
  }

  // Create User
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    setUserFormError(null)
    setUserFormSuccess(null)
    try {
      await api.post('/admin/users', {
        email: newEmail,
        password: newPassword,
        role: newRole,
      })
      setUserFormSuccess(`User ${newEmail} successfully created!`)
      setNewEmail('')
      setNewPassword('')
      usersQuery.refetch()
      auditQuery.refetch()
      setTimeout(() => {
        setShowNewUser(false)
        setUserFormSuccess(null)
      }, 2000)
    } catch (err) {
      setUserFormError((err as Error).message)
    }
  }

  // Create & Activate New Index Config
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
      setConfigSuccess(`New index configuration with base period ${configBasePeriod} activated!`)
      activeConfigQuery.refetch()
      configHistoryQuery.refetch()
      auditQuery.refetch()
      setTimeout(() => {
        setShowNewConfig(false)
        setConfigSuccess(null)
      }, 2000)
    } catch (err) {
      setConfigError((err as Error).message)
    }
  }

  return (
    <div>
      <PageHeader
        title="Administration Console"
        subtitle="Manage route weights, data ingestion sources, user accounts, and index configuration — ADMIN role required"
      />

      {/* Tabs */}
      <div className="flex border-b border-slate-200 mb-6 space-x-2">
        <TabButton active={activeTab === 'routes'} label="Route Weights" onClick={() => setActiveTab('routes')} />
        <TabButton active={activeTab === 'sources'} label="Data Sources" onClick={() => setActiveTab('sources')} />
        <TabButton active={activeTab === 'users'} label="User Management" onClick={() => setActiveTab('users')} />
        <TabButton active={activeTab === 'config'} label="Index Config" onClick={() => setActiveTab('config')} />
        <TabButton active={activeTab === 'audit'} label="Audit Log" onClick={() => setActiveTab('audit')} />
      </div>

      {/* 1. ROUTE WEIGHTS TAB */}
      {activeTab === 'routes' && (
        <Card title="Route basket weights">
          <div className="flex justify-between items-center mb-4">
            <p className="text-xs text-muted max-w-xl">
              Route weights define the basket composition for the Laspeyres index. Modifications take effect on subsequent index calculations without requiring code redeployment.
            </p>
            <button
              onClick={handleCalibrateDGCA}
              className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-medium px-3 py-1.5 rounded shadow-sm transition"
            >
              ⚡ Calibrate with DGCA Traffic Data
            </button>
          </div>

          {calibrateStatus && (
            <div className="text-xs bg-emerald-50 border border-emerald-200 text-emerald-800 p-2.5 rounded mb-4">
              {calibrateStatus}
            </div>
          )}

          {routesQuery.loading && <LoadingState />}
          {routesQuery.error && <ErrorState message={routesQuery.error} />}
          {routesQuery.data && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted border-b border-slate-200">
                    <th className="py-2">Route</th>
                    <th className="py-2">Tier</th>
                    <th className="py-2 text-right">Weight</th>
                    <th className="py-2 text-right">Status</th>
                    <th className="py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {routesQuery.data.map((r) => (
                    <tr key={r.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                      <td className="py-2 font-medium">
                        {r.origin}-{r.destination}
                      </td>
                      <td className="py-2 text-xs text-muted">{r.distance_tier ?? '—'}</td>
                      <td className="py-2 text-right">
                        {editingRouteId === r.id ? (
                          <input
                            type="number"
                            step="0.001"
                            min={0}
                            max={1}
                            value={draftWeight}
                            onChange={(e) => setDraftWeight(e.target.value)}
                            className="border border-slate-300 rounded px-2 py-0.5 w-24 text-right"
                          />
                        ) : (
                          <span className="font-mono">{(r.weight * 100).toFixed(2)}%</span>
                        )}
                      </td>
                      <td className="py-2 text-right">
                        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded ${r.active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>
                          {r.active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="py-2 text-right">
                        {editingRouteId === r.id ? (
                          <div className="space-x-2">
                            <button onClick={() => saveWeight(r.id)} className="text-blue-600 font-medium">Save</button>
                            <button onClick={() => setEditingRouteId(null)} className="text-muted">Cancel</button>
                          </div>
                        ) : (
                          <button
                            onClick={() => {
                              setEditingRouteId(r.id)
                              setDraftWeight(String(r.weight))
                              setRouteError(null)
                            }}
                            className="text-blue-600 font-medium hover:underline text-xs"
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
          {routeError && <p className="text-xs text-red-600 mt-2">{routeError}</p>}
        </Card>
      )}

      {/* 2. DATA SOURCES TAB */}
      {activeTab === 'sources' && (
        <Card title="Ingestion Data Sources">
          <p className="text-xs text-muted mb-4">
            Manage active scraping adapters and public data collection endpoints. Disabling a source excludes it from automatic background ingestion without interrupting other pipelines.
          </p>
          {sourcesQuery.loading && <LoadingState />}
          {sourcesQuery.error && <ErrorState message={sourcesQuery.error} />}
          {sourcesQuery.data && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {sourcesQuery.data.map((src) => (
                <div key={src.id} className="border border-slate-200 rounded-lg p-4 bg-white shadow-sm flex flex-col justify-between">
                  <div>
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-semibold text-slate-800 text-sm">{src.name}</h4>
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${src.active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>
                        {src.active ? 'ACTIVE' : 'DISABLED'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mb-2">Type: <span className="font-mono">{src.source_type}</span></p>
                    {src.last_success_at && (
                      <p className="text-xs text-slate-600">Last Success: {new Date(src.last_success_at).toLocaleString()}</p>
                    )}
                    {src.last_failure_reason && (
                      <p className="text-xs text-amber-700 bg-amber-50 p-1.5 rounded mt-2 border border-amber-200">
                        Notice: {src.last_failure_reason}
                      </p>
                    )}
                  </div>
                  <div className="pt-4 border-t border-slate-100 mt-3 flex justify-end">
                    <button
                      onClick={() => toggleSource(src.id)}
                      className={`text-xs px-3 py-1.5 rounded font-medium transition ${
                        src.active ? 'bg-red-50 text-red-700 hover:bg-red-100' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                      }`}
                    >
                      {src.active ? 'Disable Source' : 'Enable Source'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* 3. USER MANAGEMENT TAB */}
      {activeTab === 'users' && (
        <Card title="User Accounts & Roles">
          <div className="flex justify-between items-center mb-4">
            <p className="text-xs text-muted">
              Configure system user roles: ADMIN (full configuration), ANALYST (analytics + data export), VIEWER (read-only).
            </p>
            <button
              onClick={() => setShowNewUser(!showNewUser)}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-medium px-3 py-1.5 rounded transition"
            >
              {showNewUser ? 'Cancel' : '+ Add New User'}
            </button>
          </div>

          {showNewUser && (
            <form onSubmit={handleCreateUser} className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-6 text-sm">
              <h4 className="font-semibold mb-3 text-slate-800">Create New System Account</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-muted">Email Address</span>
                  <input
                    type="email"
                    required
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    placeholder="user@airindex.gov.in"
                    className="border border-slate-300 rounded px-2.5 py-1.5 text-xs"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-muted">Password</span>
                  <input
                    type="password"
                    required
                    minLength={6}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Min. 6 characters"
                    className="border border-slate-300 rounded px-2.5 py-1.5 text-xs"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-muted">Role</span>
                  <select
                    value={newRole}
                    onChange={(e) => setNewRole(e.target.value as any)}
                    className="border border-slate-300 rounded px-2.5 py-1.5 text-xs"
                  >
                    <option value="VIEWER">VIEWER (Read-only)</option>
                    <option value="ANALYST">ANALYST (Analysis & Exports)</option>
                    <option value="ADMIN">ADMIN (Full Control)</option>
                  </select>
                </label>
              </div>
              {userFormError && <p className="text-xs text-red-600 mb-2">{userFormError}</p>}
              {userFormSuccess && <p className="text-xs text-emerald-600 mb-2">{userFormSuccess}</p>}
              <button type="submit" className="text-xs bg-blue-600 text-white font-medium px-4 py-1.5 rounded">
                Save User
              </button>
            </form>
          )}

          {usersQuery.loading && <LoadingState />}
          {usersQuery.error && <ErrorState message={usersQuery.error} />}
          {usersQuery.data && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-slate-200">
                  <th className="py-2">User Email</th>
                  <th className="py-2">Role</th>
                  <th className="py-2 text-center">Status</th>
                  <th className="py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {usersQuery.data.map((u) => (
                  <tr key={u.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                    <td className="py-2 font-medium">{u.email}</td>
                    <td className="py-2">
                      <select
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        className="text-xs border border-slate-200 rounded px-2 py-0.5 font-medium"
                      >
                        <option value="ADMIN">ADMIN</option>
                        <option value="ANALYST">ANALYST</option>
                        <option value="VIEWER">VIEWER</option>
                      </select>
                    </td>
                    <td className="py-2 text-center">
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${u.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                        {u.is_active ? 'Active' : 'Disabled'}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      <button
                        onClick={() => toggleUserActive(u.id)}
                        className="text-xs text-slate-600 hover:text-slate-900 underline"
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {/* 4. INDEX CONFIGURATION TAB */}
      {activeTab === 'config' && (
        <Card title="Index Methodology & Period Configuration">
          <div className="flex justify-between items-center mb-4">
            <p className="text-xs text-muted max-w-xl">
              Configure active Laspeyres baseline parameters, booking window aggregation weights, and quality outlier handling rules.
            </p>
            <button
              onClick={() => setShowNewConfig(!showNewConfig)}
              className="text-xs bg-blue-600 hover:bg-blue-700 text-white font-medium px-3 py-1.5 rounded transition"
            >
              {showNewConfig ? 'Cancel' : '+ New Configuration'}
            </button>
          </div>

          {showNewConfig && (
            <form onSubmit={handleCreateConfig} className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-6 text-sm">
              <h4 className="font-semibold mb-3 text-slate-800">Deploy New Index Configuration</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-muted">Base Period (YYYY-MM)</span>
                  <input
                    type="month"
                    required
                    value={configBasePeriod}
                    onChange={(e) => setConfigBasePeriod(e.target.value)}
                    className="border border-slate-300 rounded px-2.5 py-1.5 text-xs"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-muted">Include Suspicious Outliers</span>
                  <div className="flex items-center gap-2 mt-2">
                    <input
                      type="checkbox"
                      checked={configIncludeSuspicious}
                      onChange={(e) => setConfigIncludeSuspicious(e.target.checked)}
                      className="rounded text-blue-600"
                    />
                    <span className="text-xs text-slate-700">Include SUSPICIOUS observations</span>
                  </div>
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-muted">Notes / Version Label</span>
                  <input
                    type="text"
                    value={configNotes}
                    onChange={(e) => setConfigNotes(e.target.value)}
                    placeholder="e.g. Q2 2026 calibrated baseline"
                    className="border border-slate-300 rounded px-2.5 py-1.5 text-xs"
                  />
                </label>
              </div>
              {configError && <p className="text-xs text-red-600 mb-2">{configError}</p>}
              {configSuccess && <p className="text-xs text-emerald-600 mb-2">{configSuccess}</p>}
              <button type="submit" className="text-xs bg-blue-600 text-white font-medium px-4 py-1.5 rounded">
                Activate Configuration
              </button>
            </form>
          )}

          {activeConfigQuery.data && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-xs">
              <h4 className="font-bold text-blue-900 text-sm mb-2">Active Index Baseline</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-slate-700">
                <div><span className="text-muted">Base Period:</span> <strong className="text-blue-900 font-mono">{activeConfigQuery.data.base_period}</strong></div>
                <div><span className="text-muted">Methodology:</span> <strong>{activeConfigQuery.data.methodology_version}</strong></div>
                <div><span className="text-muted">Created By:</span> <strong>{activeConfigQuery.data.created_by ?? 'System'}</strong></div>
                <div><span className="text-muted">Suspicious Rows:</span> <strong>{activeConfigQuery.data.include_suspicious ? 'Included' : 'Excluded'}</strong></div>
              </div>
            </div>
          )}

          <h4 className="font-semibold text-sm mb-2 text-slate-800">Configuration History</h4>
          {configHistoryQuery.data && (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted border-b border-slate-200">
                  <th className="py-2">Deployed At</th>
                  <th className="py-2">Base Period</th>
                  <th className="py-2">Author</th>
                  <th className="py-2">Status</th>
                  <th className="py-2">Notes</th>
                </tr>
              </thead>
              <tbody>
                {configHistoryQuery.data.map((c) => (
                  <tr key={c.id} className="border-b border-slate-100">
                    <td className="py-2">{new Date(c.created_at).toLocaleString()}</td>
                    <td className="py-2 font-mono font-semibold">{c.base_period}</td>
                    <td className="py-2">{c.created_by ?? 'seed'}</td>
                    <td className="py-2">
                      <span className={`px-2 py-0.5 rounded font-bold ${c.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-500'}`}>
                        {c.is_active ? 'ACTIVE' : 'SUPERSEDED'}
                      </span>
                    </td>
                    <td className="py-2 text-muted">{c.notes ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {/* 5. AUDIT LOG TAB */}
      {activeTab === 'audit' && (
        <Card title="System Audit Trail">
          {auditQuery.loading && <LoadingState />}
          {auditQuery.data && auditQuery.data.length === 0 && <EmptyState message="No administrative actions recorded yet." />}
          {auditQuery.data && auditQuery.data.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-muted border-b border-slate-200">
                    <th className="py-2">Timestamp</th>
                    <th className="py-2">User Email</th>
                    <th className="py-2">Action</th>
                    <th className="py-2">Target Entity</th>
                    <th className="py-2">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {auditQuery.data.map((entry) => (
                    <tr key={entry.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                      <td className="py-2 font-mono text-[11px]">{new Date(entry.timestamp).toLocaleString()}</td>
                      <td className="py-2 font-medium">{entry.user_email ?? 'System Automated'}</td>
                      <td className="py-2 font-mono text-[11px] text-blue-700 font-semibold">{entry.action}</td>
                      <td className="py-2 text-muted">
                        {entry.entity_type ? `${entry.entity_type}${entry.entity_id ? ` #${entry.entity_id}` : ''}` : '—'}
                      </td>
                      <td className="py-2 font-mono text-[10px] text-slate-500 max-w-xs truncate">
                        {entry.details ? JSON.stringify(entry.details) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

function TabButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
        active
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
      }`}
    >
      {label}
    </button>
  )
}
