import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LayoutDashboard, BarChart3, Database, Settings, LogOut, Plane } from 'lucide-react'

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

const ROLE_CHIP: Record<string, string> = {
  ADMIN: 'bg-brand-500/10 text-brand-700',
  ANALYST: 'bg-violet-500/10 text-violet-700',
  VIEWER: 'bg-slate-500/10 text-slate-600',
}

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
  const roleChip = ROLE_CHIP[(role ?? '').toUpperCase()] ?? ROLE_CHIP.VIEWER

  return (
    <div className="min-h-screen bg-base">
      {/* Ambient glow behind everything */}
      <div className="pointer-events-none fixed inset-0 bg-login-glow" aria-hidden />

      <div className="relative flex min-h-screen">
        <aside className="sticky top-0 h-screen w-[232px] shrink-0 border-r border-line bg-white/80 backdrop-blur-xl flex flex-col">
          {/* Brand */}
          <div className="flex items-center gap-3 px-5 py-5 border-b border-line">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-gradient text-white shadow-glow">
              <Plane size={18} />
            </div>
            <div>
              <div className="text-[15px] font-bold tracking-tight text-ink leading-tight">AirIndex India</div>
              <div className="text-[11px] text-muted">Airfare Price Index</div>
            </div>
          </div>

          {/* Nav */}
          <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
            {visibleItems.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `group flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-brand-500/10 text-brand-700 shadow-[inset_0_0_0_1px_rgba(20,113,232,0.15)]'
                      : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon size={17} className={isActive ? 'text-brand-600' : 'text-slate-400 group-hover:text-slate-600'} />
                    {label}
                    {isActive && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-600" />}
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Footer */}
          <div className="border-t border-line px-5 py-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[11px] text-muted">Signed in role:</span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wide ${roleChip}`}>
                {role ?? '--'}
              </span>
            </div>
            <p className="mb-3 text-[11px] leading-relaxed text-muted">
              Data sourced from the official MoSPI Consolidated CPI via esankhyiki.mospi.gov.in.
            </p>
            <button
              onClick={handleLogout}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-line px-3 py-2 text-xs font-medium text-slate-500 transition-colors hover:border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-600"
            >
              <LogOut size={14} />
              Sign out
            </button>
          </div>
        </aside>

        <main className="flex-1 min-w-0 overflow-y-auto max-w-[1120px] mx-auto w-full px-8 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}