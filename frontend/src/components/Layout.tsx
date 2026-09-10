import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LayoutDashboard, BarChart3, Database, Settings, LogOut } from 'lucide-react'

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split('.')[1]
    const json = atob(base64.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json)
  } catch {
    return null
  }
}

function useUserRole(): string | null {
  const token = localStorage.getItem('airindex_access_token')
  if (!token) return null
  const payload = decodeJwtPayload(token)
  return (payload?.role as string) ?? null
}

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/analysis', label: 'Analysis', icon: BarChart3 },
  { to: '/data', label: 'Data', icon: Database },
  { to: '/admin', label: 'Admin', icon: Settings, adminOnly: true },
]

export default function Layout() {
  const navigate = useNavigate()
  const role = useUserRole()
  const isAdmin = role === 'ADMIN'

  function handleLogout() {
    localStorage.removeItem('airindex_access_token')
    localStorage.removeItem('airindex_refresh_token')
    navigate('/login', { replace: true })
  }

  const visibleItems = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin)

  return (
    <div className="min-h-screen flex">
      <aside className="w-[220px] shrink-0 bg-white border-r border-slate-200 flex flex-col">
        <div className="px-5 py-4 border-b border-slate-200">
          <div className="text-base font-bold text-ink">AirIndex India</div>
          <div className="text-xs text-muted">Airfare Price Index</div>
        </div>
        <nav className="flex-1 overflow-y-auto py-3">
          {visibleItems.map(({ to, label, icon: Icon, end }) => (
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
          Data sourced from public government datasets.
        </div>
        <div className="border-t border-slate-200 px-5 py-3">
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-2 text-xs text-slate-600 hover:text-red-600"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto max-w-[1100px] p-8">
        <Outlet />
      </main>
    </div>
  )
}
