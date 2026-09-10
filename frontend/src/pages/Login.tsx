import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plane, ShieldCheck, TrendingUp } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'https://airindex-backend.onrender.com/api'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        setError(body.detail || `Login failed (${res.status})`)
        return
      }
      const data = await res.json()
      localStorage.setItem('airindex_access_token', data.access_token)
      localStorage.setItem('airindex_refresh_token', data.refresh_token)
      navigate('/', { replace: true })
    } catch {
      setError('Could not reach the API. Is the backend running?')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-base flex items-center justify-center p-6 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-login-glow" aria-hidden />

      <div className="relative w-full max-w-5xl grid lg:grid-cols-2 gap-10 items-center animate-fade-in-up">
        {/* Brand panel */}
        <div className="hidden lg:block">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-gradient text-white shadow-glow">
              <Plane size={24} />
            </div>
            <div>
              <div className="text-2xl font-bold tracking-tight text-ink">AirIndex India</div>
              <div className="text-sm text-muted">Real-time Airfare Price Index</div>
            </div>
          </div>
          <h2 className="mt-8 text-3xl font-bold leading-tight text-ink">
            Track the true cost of
            <br />
            <span className="bg-brand-gradient bg-clip-text text-transparent">flying in India.</span>
          </h2>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-muted">
            A continuously refreshed airfare price index built on the official MoSPI Consolidated CPI
            air transport sub-component (code 07.3.3.1, base 2024=100).
          </p>
          <div className="mt-8 space-y-3">
            <Feature label="Official MoSPI data" detail="esankhyiki.mospi.gov.in · refreshed daily" icon={<TrendingUp size={16} />} />
            <Feature label="Transparent methodology" detail="Route-weighted index, base 2024 = 100" icon={<ShieldCheck size={16} />} />
          </div>
        </div>

        {/* Login card */}
        <div className="mx-auto w-full max-w-sm">
          <div className="rounded-2xl border border-line bg-surface/80 p-8 shadow-card backdrop-blur-xl">
            <div className="mb-6 flex items-center gap-3 lg:hidden">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-gradient text-white">
                <Plane size={20} />
              </div>
              <div>
                <div className="text-lg font-bold text-ink">AirIndex India</div>
                <div className="text-xs text-muted">Airfare Price Index Platform</div>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5" htmlFor="email">
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-line bg-raised px-3.5 py-2.5 text-sm text-ink placeholder:text-slate-600 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/60 focus:border-brand-500/50"
                  placeholder="you@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-line bg-raised px-3.5 py-2.5 text-sm text-ink placeholder:text-slate-600 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/60 focus:border-brand-500/50"
                  placeholder="Enter your password"
                />
              </div>
              {error && (
                <div className="text-sm text-rose-200 bg-rose-500/10 border border-rose-500/30 rounded-lg px-3 py-2.5">
                  {error}
                </div>
              )}
              <button
                type="submit"
                disabled={submitting || !email || !password}
                className="w-full rounded-lg bg-brand-gradient px-4 py-2.5 text-sm font-semibold text-white shadow-glow transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {submitting ? 'Signing in…' : 'Sign In'}
              </button>
            </form>

            <p className="mt-6 text-center text-[11px] text-muted">
              Access is restricted to authorized platform users.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function Feature({ label, detail, icon }: { label: string; detail: string; icon: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-raised text-brand-400">
        {icon}
      </div>
      <div>
        <div className="text-sm font-semibold text-ink">{label}</div>
        <div className="text-xs text-muted">{detail}</div>
      </div>
    </div>
  )
}