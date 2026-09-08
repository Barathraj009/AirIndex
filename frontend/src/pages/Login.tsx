import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plane } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

type Step = 'email' | 'credentials'

export default function Login() {
  const navigate = useNavigate()

  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Credentials state
  const [userExists, setUserExists] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  async function handleCheckEmail(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const res = await fetch(`${API_BASE}/auth/check-user`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      if (res.ok) {
        const data = await res.json()
        setUserExists(data.exists)
      } else {
        setUserExists(false)
      }
      setStep('credentials')
    } catch {
      setError('Could not reach the API. Is the backend running?')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (userExists) {
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
      } else {
        if (!username.trim()) {
          setError('Username is required')
          return
        }
        if (password.length < 4) {
          setError('Password must be at least 4 characters')
          return
        }
        const res = await fetch(`${API_BASE}/auth/seed-user`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            username: username.trim(),
            password,
          }),
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          setError(body.detail || `Registration failed (${res.status})`)
          return
        }
        const loginRes = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })
        if (!loginRes.ok) {
          const body = await loginRes.json().catch(() => ({}))
          setError(body.detail || `Login failed (${loginRes.status})`)
          return
        }
        const data = await loginRes.json()
        localStorage.setItem('airindex_access_token', data.access_token)
        localStorage.setItem('airindex_refresh_token', data.refresh_token)
        navigate('/', { replace: true })
      }
    } catch {
      setError('Could not reach the API. Is the backend running?')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center text-white">
              <Plane size={20} />
            </div>
            <div>
              <div className="text-lg font-bold text-ink">AirIndex India</div>
              <div className="text-xs text-muted">SIH 2026 · PS 26056</div>
            </div>
          </div>

          {step === 'email' && (
            <form onSubmit={handleCheckEmail} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="email">
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="your-email@gmail.com"
                />
              </div>
              {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</div>}
              <button
                type="submit"
                disabled={submitting || !email}
                className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {submitting ? 'Checking...' : 'Continue'}
              </button>
            </form>
          )}

          {step === 'credentials' && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="text-sm text-slate-600">
                {userExists ? (
                  <span>Sign in as <span className="font-medium text-slate-800">{email}</span></span>
                ) : (
                  <span>Create account for <span className="font-medium text-slate-800">{email}</span></span>
                )}
              </div>
              {!userExists && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="username">Username</label>
                  <input
                    id="username"
                    type="text"
                    required
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Choose a username"
                  />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="password">
                  {userExists ? 'Password' : 'Create password'}
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  autoComplete={userExists ? 'current-password' : 'new-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={userExists ? 'Enter your password' : 'At least 4 characters'}
                />
              </div>
              {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</div>}
              <button
                type="submit"
                disabled={submitting || !password}
                className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {submitting ? 'Please wait...' : userExists ? 'Sign in' : 'Create account & sign in'}
              </button>
              <button
                type="button"
                onClick={() => { setStep('email'); setPassword(''); setError(null); setUsername('') }}
                className="w-full text-xs text-slate-500 hover:text-slate-700"
              >
                Back
              </button>
            </form>
          )}
        </div>
        <p className="mt-4 text-center text-xs text-muted">
          {userExists ? 'Enter your password to sign in' : 'First time? We\'ll create your account.'}
        </p>
      </div>
    </div>
  )
}
