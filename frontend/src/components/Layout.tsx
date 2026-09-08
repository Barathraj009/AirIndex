import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, Map, Grid3x3, Clock, Plane, Database,
  ShieldCheck, Radar, LineChart, BookOpen, FileCode, Settings, LogOut,
  Compass, Calculator, KeyRound,
} from 'lucide-react'
import { api } from '../api/client'

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/index', label: 'Airfare Price Index', icon: TrendingUp },
  { to: '/cpi-simulator', label: 'CPI Augmentation', icon: Calculator },
  { to: '/geospatial-map', label: 'Geospatial Map', icon: Compass },
  { to: '/routes', label: 'Route Analysis', icon: Map },
  { to: '/heatmap', label: 'Sector Heatmap', icon: Grid3x3 },
  { to: '/lead-time', label: 'Lead-Time Analysis', icon: Clock },
  { to: '/airlines', label: 'Airline Analysis', icon: Plane },
  { to: '/explorer', label: 'Data Explorer', icon: Database },
  { to: '/quality', label: 'Data Quality', icon: ShieldCheck },
  { to: '/scraping', label: 'Collection Monitor', icon: Radar },
  { to: '/backtesting', label: 'Backtesting', icon: LineChart },
  { to: '/methodology', label: 'Methodology', icon: BookOpen },
  { to: '/api-docs', label: 'API Documentation', icon: FileCode },
  { to: '/admin', label: 'Administration', icon: Settings },
]

export default function Layout() {
  const navigate = useNavigate()
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [passwordMsg, setPasswordMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [loadingPassword, setLoadingPassword] = useState(false)

  function handleLogout() {
    localStorage.removeItem('airindex_access_token')
    localStorage.removeItem('airindex_refresh_token')
    navigate('/login', { replace: true })
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault()
    setPasswordMsg(null)
    setLoadingPassword(true)
    try {
      await api.post('/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
      })
      setPasswordMsg({ type: 'success', text: 'Password successfully updated!' })
      setOldPassword('')
      setNewPassword('')
      setTimeout(() => {
        setShowPasswordModal(false)
        setPasswordMsg(null)
      }, 1500)
    } catch (err) {
      setPasswordMsg({ type: 'error', text: (err as Error).message })
    } finally {
      setLoadingPassword(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      <aside className="w-64 shrink-0 bg-white border-r border-slate-200 flex flex-col">
        <div className="px-5 py-4 border-b border-slate-200">
          <div className="text-base font-bold text-ink">AirIndex India</div>
          <div className="text-xs text-muted">SIH 2026 · PS 26056</div>
        </div>
        <nav className="flex-1 overflow-y-auto py-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm font-medium ${
                  isActive ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-600' : 'text-slate-600 hover:bg-slate-50'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-3 border-t border-slate-200 text-[11px] text-muted">
          All figures may include DEMO/SIMULATED data — check source labels.
        </div>
        <div className="border-t border-slate-200 px-5 py-3 space-y-2">
          <button
            onClick={() => setShowPasswordModal(true)}
            className="flex w-full items-center gap-2 text-xs text-slate-600 hover:text-slate-900"
          >
            <KeyRound size={14} />
            Change Password
          </button>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-2 text-xs text-slate-600 hover:text-red-600"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto p-8 max-w-6xl">
        <Outlet />
      </main>

      {/* Change Password Modal */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 border border-slate-200">
            <h3 className="text-base font-bold text-slate-900 mb-1">Update Account Password</h3>
            <p className="text-xs text-muted mb-4">Rotate demo credentials to secure your administrative session.</p>

            <form onSubmit={handleChangePassword} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Current Password</label>
                <input
                  type="password"
                  required
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  placeholder="Enter current password"
                  className="w-full border border-slate-300 rounded px-2.5 py-1.5"
                />
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">New Password</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Min. 6 characters"
                  className="w-full border border-slate-300 rounded px-2.5 py-1.5"
                />
              </div>

              {passwordMsg && (
                <div
                  className={`p-2.5 rounded text-xs ${
                    passwordMsg.type === 'success'
                      ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                      : 'bg-red-50 text-red-800 border border-red-200'
                  }`}
                >
                  {passwordMsg.text}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => {
                    setShowPasswordModal(false)
                    setPasswordMsg(null)
                  }}
                  className="px-3 py-1.5 text-slate-600 hover:bg-slate-100 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loadingPassword}
                  className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded disabled:opacity-50"
                >
                  {loadingPassword ? 'Updating…' : 'Save Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
