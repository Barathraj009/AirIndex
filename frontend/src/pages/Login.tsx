import { FormEvent, useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plane, Mail, KeyRound } from 'lucide-react'

type Tab = 'password' | 'otp'

export default function Login() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('password')

  // Password login state
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // OTP state
  const [otpEmail, setOtpEmail] = useState('')
  const [otpStep, setOtpStep] = useState<'email' | 'otp'>('email')
  const [otpCode, setOtpCode] = useState('')
  const [otpError, setOtpError] = useState<string | null>(null)
  const [otpSubmitting, setOtpSubmitting] = useState(false)
  const [maskedEmail, setMaskedEmail] = useState('')
  const [resendCooldown, setResendCooldown] = useState(0)

  useEffect(() => {
    if (resendCooldown <= 0) return
    const t = setTimeout(() => setResendCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [resendCooldown])

  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const res = await fetch('/api/auth/login', {
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

  const handleSendOtp = useCallback(async () => {
    setOtpError(null)
    setOtpSubmitting(true)
    try {
      const res = await fetch('/otp-auth/api/auth/send-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: otpEmail }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        setOtpError(body.detail || body.message || `Failed to send code (${res.status})`)
        return
      }
      const data = await res.json()
      setMaskedEmail(data.maskedEmail || otpEmail)
      setResendCooldown(data.resendCooldownSeconds || 45)
      setOtpStep('otp')
    } catch {
      setOtpError('Could not reach the OTP service. Is it running on port 4000?')
    } finally {
      setOtpSubmitting(false)
    }
  }, [otpEmail])

  async function handleVerifyOtp(e: FormEvent) {
    e.preventDefault()
    setOtpError(null)
    setOtpSubmitting(true)
    try {
      const verifyRes = await fetch('/otp-auth/api/auth/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: otpEmail, otp: otpCode }),
      })
      if (!verifyRes.ok) {
        const body = await verifyRes.json().catch(() => ({}))
        setOtpError(body.detail || body.message || `Verification failed (${verifyRes.status})`)
        return
      }
      const verifyData = await verifyRes.json()

      const exchangeRes = await fetch('/api/auth/otp/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ otp_token: verifyData.token, email: verifyData.email }),
      })
      if (!exchangeRes.ok) {
        const body = await exchangeRes.json().catch(() => ({}))
        setOtpError(body.detail || `Exchange failed (${exchangeRes.status})`)
        return
      }
      const exchangeData = await exchangeRes.json()
      localStorage.setItem('airindex_access_token', exchangeData.access_token)
      localStorage.setItem('airindex_refresh_token', exchangeData.refresh_token)
      navigate('/', { replace: true })
    } catch {
      setOtpError('Could not reach the API. Is the backend running?')
    } finally {
      setOtpSubmitting(false)
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

          <div className="flex border border-slate-200 rounded-md mb-6 overflow-hidden">
            <button
              type="button"
              onClick={() => { setTab('password'); setError(null) }}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium transition-colors ${
                tab === 'password' ? 'bg-blue-600 text-white' : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
              }`}
            >
              <KeyRound size={14} />
              Password
            </button>
            <button
              type="button"
              onClick={() => { setTab('otp'); setOtpError(null) }}
              className={`flex-1 flex items-center justify-center gap-2 py-2 text-sm font-medium transition-colors ${
                tab === 'otp' ? 'bg-blue-600 text-white' : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
              }`}
            >
              <Mail size={14} />
              Email OTP
            </button>
          </div>

          {tab === 'password' && (
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="email">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="admin@airindex.gov.in"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</div>}

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {submitting ? 'Signing in…' : 'Sign in'}
              </button>
            </form>
          )}

          {tab === 'otp' && otpStep === 'email' && (
            <form onSubmit={(e) => { e.preventDefault(); handleSendOtp() }} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="otp-email">
                  Email
                </label>
                <input
                  id="otp-email"
                  type="email"
                  required
                  autoComplete="username"
                  value={otpEmail}
                  onChange={(e) => setOtpEmail(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="admin@airindex.gov.in"
                />
              </div>

              {otpError && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{otpError}</div>}

              <button
                type="submit"
                disabled={otpSubmitting}
                className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {otpSubmitting ? 'Sending…' : 'Send code'}
              </button>
            </form>
          )}

          {tab === 'otp' && otpStep === 'otp' && (
            <form onSubmit={handleVerifyOtp} className="space-y-4">
              <div className="text-sm text-slate-600">
                Code sent to <span className="font-medium text-slate-800">{maskedEmail}</span>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1" htmlFor="otp-code">
                  Verification code
                </label>
                <input
                  id="otp-code"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  autoComplete="one-time-code"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm tracking-[0.5em] text-center font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="000000"
                />
              </div>

              {otpError && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{otpError}</div>}

              <button
                type="submit"
                disabled={otpSubmitting || otpCode.length !== 6}
                className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {otpSubmitting ? 'Verifying…' : 'Verify'}
              </button>

              <div className="text-center">
                {resendCooldown > 0 ? (
                  <span className="text-xs text-slate-400">Resend code in {resendCooldown}s</span>
                ) : (
                  <button
                    type="button"
                    onClick={handleSendOtp}
                    disabled={otpSubmitting}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                  >
                    Resend code
                  </button>
                )}
              </div>

              <button
                type="button"
                onClick={() => { setOtpStep('email'); setOtpCode(''); setOtpError(null) }}
                className="w-full text-xs text-slate-500 hover:text-slate-700"
              >
                Use a different email
              </button>
            </form>
          )}
        </div>
        <p className="mt-4 text-center text-xs text-muted">
          Use the administrator account provisioned during seeding (see the project README).
        </p>
      </div>
    </div>
  )
}
