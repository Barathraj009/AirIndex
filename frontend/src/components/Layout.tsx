import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, Map, Grid3x3, Clock, Plane, Database,
  ShieldCheck, Radar, LineChart, BookOpen, FileCode, Settings, LogOut,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/index', label: 'Airfare Price Index', icon: TrendingUp },
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
  function handleLogout() {
    localStorage.removeItem('airindex_access_token')
    localStorage.removeItem('airindex_refresh_token')
    navigate('/login', { replace: true })
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
        <div className="border-t border-slate-200 px-5 py-3">
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-2 text-sm text-slate-600 hover:text-red-600"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-8 max-w-6xl">
        <Outlet />
      </main>
    </div>
  )
}
